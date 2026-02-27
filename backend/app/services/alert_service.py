"""
异常行为告警服务

异步检测异常行为，通过 AWS SNS 发送告警，支持冷却期防重复告警。
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytz

from app.models.alert import AlertEvent, AlertRule
from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.system_config import SystemConfig
from app.services.audit_service import AuditEventType

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, db_session_factory, sns_client=None):
        self._db_factory = db_session_factory
        self._sns = sns_client  # boto3 SNS client（可选）

    async def check_and_alert(
        self,
        event_type: str,
        user_id: Optional[int],
        client_ip: Optional[str],
        event_time: Optional[datetime] = None,
        username: Optional[str] = None,
    ) -> None:
        """
        异步执行，通过 BackgroundTasks 调用，不阻塞主请求。
        根据 event_type 执行对应检测逻辑。
        """
        if event_time is None:
            event_time = datetime.utcnow()

        db = self._db_factory()
        try:
            rules = {r.rule_key: r for r in db.query(AlertRule).filter_by(enabled=True).all()}
            configs = {c.key: c.value for c in db.query(SystemConfig).all()}
            cooldown_minutes = int(configs.get("alert_cooldown_minutes", "30"))

            triggered = []

            # 检测：会话创建频率
            if event_type == AuditEventType.SESSION_CREATE and user_id:
                rule = rules.get("session_burst")
                if rule and self._check_session_burst(db, user_id, rule.time_window_minutes, rule.threshold):
                    triggered.append(("session_burst", user_id, username, client_ip))

            # 检测：登录失败次数
            if event_type == AuditEventType.LOGIN and client_ip:
                rule = rules.get("login_failure")
                if rule and self._check_login_failure(db, client_ip, rule.time_window_minutes, rule.threshold):
                    triggered.append(("login_failure", user_id, username, client_ip))

            # 检测：多 IP 登录
            if event_type == AuditEventType.LOGIN and user_id:
                rule = rules.get("multi_ip_login")
                if rule and self._check_multi_ip(db, user_id, rule.time_window_minutes // 60 or 1, rule.threshold):
                    triggered.append(("multi_ip_login", user_id, username, client_ip))

            # 检测：非工作时间登录
            if event_type == AuditEventType.LOGIN and user_id:
                rule = rules.get("offhour_login")
                if rule:
                    start = configs.get("alert_offhour_start", "22:00")
                    end = configs.get("alert_offhour_end", "08:00")
                    tz = configs.get("alert_offhour_tz", "Asia/Shanghai")
                    if self._check_offhour(event_time, start, end, tz):
                        triggered.append(("offhour_login", user_id, username, client_ip))

            # 处理触发的告警
            sns_topic = configs.get("sns_topic_arn", "")
            for rule_key, trig_user_id, trig_username, trig_ip in triggered:
                if self._in_cooldown(db, rule_key, trig_user_id, cooldown_minutes):
                    continue
                detail = {
                    "rule_key": rule_key,
                    "user_id": trig_user_id,
                    "username": trig_username,
                    "client_ip": trig_ip,
                    "event_time": event_time.isoformat(),
                }
                event = AlertEvent(
                    rule_key=rule_key,
                    triggered_user_id=trig_user_id,
                    triggered_username=trig_username,
                    triggered_at=event_time,
                    event_detail=json.dumps(detail, ensure_ascii=False),
                    notification_sent=False,
                )
                db.add(event)
                db.commit()
                db.refresh(event)

                if sns_topic:
                    await self._send_sns(db, event, sns_topic, rule_key, detail)
        except Exception as e:
            logger.error(f"AlertService.check_and_alert error: {e}", exc_info=True)
        finally:
            db.close()

    def _check_session_burst(self, db, user_id: int, window_minutes: int, threshold: int) -> bool:
        """同一用户在 window_minutes 内创建会话次数超过 threshold"""
        since = datetime.utcnow() - timedelta(minutes=window_minutes)
        count = (
            db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.started_at >= since,
            )
            .count()
        )
        return count > threshold

    def _check_login_failure(self, db, client_ip: str, window_minutes: int, threshold: int) -> bool:
        """同一 IP 在 window_minutes 内登录失败次数超过 threshold"""
        since = datetime.utcnow() - timedelta(minutes=window_minutes)
        count = (
            db.query(AuditLog)
            .filter(
                AuditLog.event_type == AuditEventType.LOGIN,
                AuditLog.client_ip == client_ip,
                AuditLog.result == "failure",
                AuditLog.event_time >= since,
            )
            .count()
        )
        return count > threshold

    def _check_multi_ip(self, db, user_id: int, window_hours: int, threshold: int) -> bool:
        """同一账号在 window_hours 内从超过 threshold 个不同 IP 登录"""
        since = datetime.utcnow() - timedelta(hours=window_hours)
        from sqlalchemy import func
        count = (
            db.query(func.count(func.distinct(AuditLog.client_ip)))
            .filter(
                AuditLog.event_type == AuditEventType.LOGIN,
                AuditLog.user_id == user_id,
                AuditLog.result == "success",
                AuditLog.event_time >= since,
            )
            .scalar()
        )
        return (count or 0) > threshold

    def _check_offhour(self, event_time: datetime, start: str, end: str, tz: str) -> bool:
        """
        将 UTC event_time 转换为配置时区后，判断是否在非工作时间段内。
        支持跨午夜时间段（如 22:00-08:00）。
        """
        try:
            tz_obj = pytz.timezone(tz)
            local_time = event_time.replace(tzinfo=pytz.utc).astimezone(tz_obj)
            local_hm = local_time.hour * 60 + local_time.minute

            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_total = start_h * 60 + start_m
            end_total = end_h * 60 + end_m

            if start_total > end_total:
                # 跨午夜：如 22:00-08:00
                return local_hm >= start_total or local_hm < end_total
            else:
                return start_total <= local_hm < end_total
        except Exception as e:
            logger.warning(f"offhour check error: {e}")
            return False

    def _in_cooldown(self, db, rule_key: str, user_id: Optional[int], cooldown_minutes: int) -> bool:
        """检查同用户同规则是否在冷却期内"""
        since = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
        query = db.query(AlertEvent).filter(
            AlertEvent.rule_key == rule_key,
            AlertEvent.triggered_at >= since,
        )
        if user_id:
            query = query.filter(AlertEvent.triggered_user_id == user_id)
        return query.first() is not None

    async def _send_sns(self, db, event: AlertEvent, topic_arn: str, rule_key: str, detail: Dict[str, Any]):
        """boto3 SNS publish，失败时重试最多 3 次（间隔 60 秒）"""
        if not self._sns:
            try:
                import boto3
                # 从 SNS ARN 中提取 region
                # ARN 格式: arn:aws-cn:sns:cn-northwest-1:123456789012:topic-name
                region = self._extract_region_from_arn(topic_arn)
                self._sns = boto3.client("sns", region_name=region)
            except Exception as e:
                logger.error(f"Failed to create SNS client: {e}")
                return

        subject = f"[KiroCLI Alert] {rule_key}"
        message = (
            f"告警类型: {rule_key}\n"
            f"用户: {detail.get('username') or detail.get('user_id', 'unknown')}\n"
            f"IP: {detail.get('client_ip', 'unknown')}\n"
            f"时间: {detail.get('event_time', '')}\n"
        )

        for attempt in range(3):
            try:
                self._sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
                event.notification_sent = True
                db.commit()
                return
            except Exception as e:
                logger.warning(f"SNS publish attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(60)

        # 3 次全部失败
        event.notification_error = f"SNS publish failed after 3 attempts"
        db.commit()

    @staticmethod
    def _extract_region_from_arn(arn: str) -> str:
        """
        从 ARN 中提取 region
        ARN 格式: arn:aws-cn:sns:cn-northwest-1:123456789012:topic-name
        """
        try:
            parts = arn.split(":")
            if len(parts) >= 4:
                return parts[3]
        except Exception as e:
            logger.warning(f"Failed to extract region from ARN {arn}: {e}")
        # 回退到配置文件中的 region
        from app.config import settings
        return settings.AWS_REGION

