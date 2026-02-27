from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.v1.dependencies import require_admin
from app.core.database import get_db
from app.models.alert import AlertEvent, AlertRule
from app.models.group import GroupRoleMapping, UserGroup
from app.models.permission import UserPermission
from app.models.session import Session as SessionModel
from app.models.system_config import SystemConfig
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.ip_whitelist_service import IPWhitelistService
from app.services.user_service import UserService

router = APIRouter()
_ip_whitelist_service = IPWhitelistService()
_audit_service = AuditService()


def _get_client_ip(request: Request) -> str:
    """从请求头解析客户端真实 IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


@router.post("/users/sync")
async def sync_users(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    try:
        stats = service.sync_from_iam()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    total = query.count()
    users = query.offset(offset).limit(limit).all()

    service = UserService(db)
    user_list = []
    for u in users:
        # 获取用户权限配置
        perm = service.get_user_permissions(u.id)
        daily_quota = perm.daily_session_quota if perm else 10
        
        # 获取今日已用会话数
        today_used = service.get_user_total_sessions(u.id, today_only=True)
        
        user_list.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "status": u.status,
            "last_login_at": u.last_login_at,
            "today_sessions": today_used,        # 今日已用
            "daily_quota": daily_quota,          # 每日配额
            "total_sessions": service.get_user_total_sessions(u.id),  # 保留总会话数
        })

    return {"success": True, "data": {"users": user_list, "total": total, "limit": limit, "offset": offset}}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = UserService(db)
    groups = service.get_user_groups(user_id)
    perm = service.get_user_permissions(user_id)
    total_sessions = service.get_user_total_sessions(user_id)

    recent_sessions = (
        db.query(SessionModel)
        .filter_by(user_id=user_id)
        .order_by(SessionModel.started_at.desc())
        .limit(5)
        .all()
    )

    permissions = {}
    if perm:
        permissions = {
            "max_concurrent_sessions": perm.max_concurrent_sessions,
            "max_session_duration_hours": perm.max_session_duration_hours,
            "daily_session_quota": perm.daily_session_quota,
            "can_start_terminal": perm.can_start_terminal,
            "can_view_monitoring": perm.can_view_monitoring,
            "can_export_data": perm.can_export_data,
        }

    return {
        "success": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
            "groups": groups,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "permissions": permissions,
            "statistics": {
                "total_sessions": total_sessions,
                "recent_sessions": [
                    {"id": s.id, "started_at": s.started_at, "duration_seconds": s.duration_seconds}
                    for s in recent_sessions
                ],
            },
        },
    }


@router.put("/users/{user_id}/permissions")
async def update_permissions(
    user_id: int,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    try:
        service.update_permissions(user_id, body)
        return {"success": True, "message": "Permissions updated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/groups")
async def list_groups(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    mappings = db.query(GroupRoleMapping).all()
    groups = []
    for m in mappings:
        member_count = db.query(UserGroup).filter_by(group_name=m.group_name).count()
        groups.append({
            "id": m.id,
            "group_name": m.group_name,
            "role": m.role,
            "member_count": member_count,
        })
    return {"success": True, "data": {"groups": groups}}


@router.get("/groups/{group_id}/role")
async def get_group_role(
    group_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    mapping = db.query(GroupRoleMapping).filter_by(id=group_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"success": True, "data": {"group_name": mapping.group_name, "role": mapping.role}}


@router.put("/groups/{group_id}/role")
async def update_group_role(
    group_id: int,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    mapping = db.query(GroupRoleMapping).filter_by(id=group_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Group not found")
    role = body.get("role")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role")
    mapping.role = role
    db.commit()
    return {"success": True, "message": "Group role updated"}


# ─── IP 白名单 ────────────────────────────────────────────────────────────────

@router.get("/ip-whitelist/my-ip")
async def get_my_ip(
    request: Request,
    current_user=Depends(require_admin),
):
    """返回当前请求者的出口 IP"""
    ip = _get_client_ip(request)
    return {"success": True, "data": {"ip": ip}}


@router.get("/ip-whitelist")
async def get_ip_whitelist(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """返回 IP 白名单启用状态和条目列表"""
    data = _ip_whitelist_service.get_whitelist(db)
    return {"success": True, "data": data}


@router.put("/ip-whitelist")
async def update_ip_whitelist(
    request: Request,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """全量更新 IP 白名单（含自锁校验）"""
    enabled = body.get("enabled", False)
    entries = body.get("entries", [])
    requester_ip = _get_client_ip(request)

    try:
        _ip_whitelist_service.update_whitelist(db, enabled, entries, requester_ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (PermissionError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=f"Nginx 配置更新失败: {e}")

    return {"success": True, "message": "白名单已更新，Nginx 配置已重载"}


# ─── 审计日志 ─────────────────────────────────────────────────────────────────

@router.get("/audit-logs/export")
async def export_audit_logs(
    user_id: Optional[int] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """导出审计日志为 CSV 文件"""
    from datetime import datetime
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if event_type:
        filters["event_type"] = event_type
    if start_time:
        try:
            filters["start_time"] = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    if end_time:
        try:
            filters["end_time"] = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format")
    return _audit_service.export_csv(db, filters)


@router.get("/audit-logs")
async def get_audit_logs(
    user_id: Optional[int] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查询审计日志，支持过滤和分页"""
    from datetime import datetime
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if event_type:
        filters["event_type"] = event_type
    if start_time:
        try:
            filters["start_time"] = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    if end_time:
        try:
            filters["end_time"] = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format")

    logs, total = _audit_service.query_logs(db, filters, limit=limit, offset=offset)
    return {
        "success": True,
        "data": {
            "logs": [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "user_id": log.user_id,
                    "username": log.username,
                    "client_ip": log.client_ip,
                    "user_agent": log.user_agent,
                    "event_time": log.event_time.isoformat() if log.event_time else None,
                    "event_detail": log.event_detail,
                    "result": log.result,
                }
                for log in logs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


# ─── 告警规则 ─────────────────────────────────────────────────────────────────

_ALERT_CONFIG_KEYS = [
    "alert_offhour_start",
    "alert_offhour_end",
    "alert_offhour_tz",
    "alert_cooldown_minutes",
    "sns_topic_arn",
]


@router.get("/alert-rules")
async def get_alert_rules(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """返回所有告警规则配置及 SNS/非工作时间/冷却期配置"""
    rules = db.query(AlertRule).all()
    configs = {c.key: c.value for c in db.query(SystemConfig).filter(SystemConfig.key.in_(_ALERT_CONFIG_KEYS)).all()}
    return {
        "success": True,
        "data": {
            "rules": [
                {
                    "id": r.id,
                    "rule_key": r.rule_key,
                    "rule_name": r.rule_name,
                    "time_window_minutes": r.time_window_minutes,
                    "threshold": r.threshold,
                    "enabled": r.enabled,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rules
            ],
            "config": {
                "offhour_start": configs.get("alert_offhour_start", "22:00"),
                "offhour_end": configs.get("alert_offhour_end", "08:00"),
                "offhour_tz": configs.get("alert_offhour_tz", "Asia/Shanghai"),
                "cooldown_minutes": int(configs.get("alert_cooldown_minutes", "30")),
                "sns_topic_arn": configs.get("sns_topic_arn", ""),
            },
        },
    }


@router.put("/alert-rules")
async def update_alert_rules(
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新告警规则阈值、时间窗口、非工作时间段、冷却期、SNS Topic ARN"""
    now = datetime.utcnow()

    # 更新规则列表
    rules_data = body.get("rules", [])
    for rd in rules_data:
        rule = db.query(AlertRule).filter_by(rule_key=rd.get("rule_key")).first()
        if not rule:
            continue
        if "time_window_minutes" in rd:
            rule.time_window_minutes = int(rd["time_window_minutes"])
        if "threshold" in rd:
            rule.threshold = int(rd["threshold"])
        if "enabled" in rd:
            rule.enabled = bool(rd["enabled"])
        rule.updated_at = now

    # 更新系统配置
    config_map = body.get("config", {})
    key_map = {
        "offhour_start": "alert_offhour_start",
        "offhour_end": "alert_offhour_end",
        "offhour_tz": "alert_offhour_tz",
        "cooldown_minutes": "alert_cooldown_minutes",
        "sns_topic_arn": "sns_topic_arn",
    }
    for field, db_key in key_map.items():
        if field in config_map:
            cfg = db.query(SystemConfig).filter_by(key=db_key).first()
            if cfg:
                cfg.value = str(config_map[field])
                cfg.updated_at = now
            else:
                db.add(SystemConfig(key=db_key, value=str(config_map[field]), updated_at=now))

    db.commit()
    return {"success": True, "message": "告警规则已更新"}


@router.get("/alert-events")
async def get_alert_events(
    rule_key: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """返回历史告警记录，支持分页和时间过滤"""
    query = db.query(AlertEvent)
    if rule_key:
        query = query.filter_by(rule_key=rule_key)
    if start_time:
        try:
            query = query.filter(AlertEvent.triggered_at >= datetime.fromisoformat(start_time))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    if end_time:
        try:
            query = query.filter(AlertEvent.triggered_at <= datetime.fromisoformat(end_time))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format")

    total = query.count()
    events = query.order_by(AlertEvent.triggered_at.desc()).offset(offset).limit(limit).all()
    return {
        "success": True,
        "data": {
            "events": [
                {
                    "id": e.id,
                    "rule_key": e.rule_key,
                    "triggered_user_id": e.triggered_user_id,
                    "triggered_username": e.triggered_username,
                    "triggered_at": e.triggered_at.isoformat() if e.triggered_at else None,
                    "event_detail": e.event_detail,
                    "notification_sent": e.notification_sent,
                    "notification_error": e.notification_error,
                }
                for e in events
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


# ─── SNS 测试发送 ─────────────────────────────────────────────────────────────

@router.post("/alert-rules/test-sns")
async def test_sns_notification(
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """向指定 SNS Topic 发送测试消息"""
    import boto3
    from botocore.exceptions import ClientError

    topic_arn = body.get("sns_topic_arn", "").strip()
    if not topic_arn:
        raise HTTPException(status_code=400, detail="sns_topic_arn is required")

    try:
        # 从 SNS ARN 中提取 region
        # ARN 格式: arn:aws-cn:sns:cn-northwest-1:123456789012:topic-name
        region = _extract_region_from_arn(topic_arn)
        sns = boto3.client("sns", region_name=region)
        sns.publish(
            TopicArn=topic_arn,
            Subject="[KiroCLI] SNS 测试通知",
            Message=f"这是来自 KiroCLI Platform 的测试消息，由管理员 {current_user.username} 触发。",
        )
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"SNS 发送失败: {e.response['Error']['Message']}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SNS 发送失败: {str(e)}")

    return {"success": True, "message": "测试消息已发送"}


def _extract_region_from_arn(arn: str) -> str:
    """
    从 ARN 中提取 region
    ARN 格式: arn:aws-cn:sns:cn-northwest-1:123456789012:topic-name
    """
    try:
        parts = arn.split(":")
        if len(parts) >= 4:
            return parts[3]
    except Exception:
        pass
    # 回退到配置文件中的 region
    from app.config import settings
    return settings.AWS_REGION


# ─── 强制下线 ─────────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/force-logout")
async def force_logout_user(
    user_id: int,
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """强制下线指定用户：撤销所有 Refresh Token、关闭所有活动会话"""
    from app.services.gotty_service import gotty_service
    from app.services.token_service import token_service

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 撤销所有 Refresh Token（立即生效，用户无法续期）
    token_service.revoke_all_user_tokens(db, user_id)

    # 注意：Access Token 无法在此处主动加入黑名单。
    # Access Token 以 HttpOnly Cookie 形式存储在用户浏览器端，
    # 服务端无法主动获取其值（jti），因此无法将其加入黑名单。
    # Access Token 将在其自然过期时间（8 小时）后失效。
    # 由于 Refresh Token 已被立即撤销，用户在 Access Token 过期后
    # 将无法续期，必须重新登录。

    # 关闭所有活动 Gotty 会话
    active_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user_id,
            SessionModel.status.in_(["starting", "running"]),
        )
        .all()
    )
    from datetime import datetime
    for sess in active_sessions:
        try:
            await gotty_service.stop_gotty(sess.gotty_pid, sess.gotty_port)
        except Exception:
            pass
        sess.status = "closed"
        sess.closed_at = datetime.utcnow()
    db.commit()

    # 审计日志
    _audit_service.log(
        db, "ADMIN_FORCE_LOGOUT",
        current_user.id, current_user.username,
        _get_client_ip(request), request.headers.get("User-Agent", ""),
        {"target_user_id": user_id, "target_username": user.username},
        "success",
    )

    return {"success": True, "message": f"用户 {user.username} 已强制下线"}


# ─── Secrets Manager 状态 ────────────────────────────────────────────────────

@router.get("/secrets/status")
async def get_secrets_status(
    current_user=Depends(require_admin),
):
    """返回各配置项的加载来源，不返回配置值本身"""
    from app.config import settings
    from app.services.secrets_manager import secrets_loader

    sources = secrets_loader.get_load_sources()

    def _source(key: str, value) -> str:
        if key in sources:
            return sources[key]
        if value:
            return "env_file"
        return "not_configured"

    return {
        "success": True,
        "data": {
            "SECRET_KEY": {"source": _source("SECRET_KEY", settings.SECRET_KEY)},
            "SAML_IDP_X509_CERT": {"source": _source("SAML_IDP_X509_CERT", settings.SAML_IDP_X509_CERT)},
            "SAML_SP_PRIVATE_KEY": {"source": _source("SAML_SP_PRIVATE_KEY", getattr(settings, "SAML_SP_PRIVATE_KEY", None))},
            "secrets_manager_enabled": settings.SECRETS_MANAGER_ENABLED,
            "secret_name": settings.SECRETS_MANAGER_SECRET_NAME,
        },
    }
