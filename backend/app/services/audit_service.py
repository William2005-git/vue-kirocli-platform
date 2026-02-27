"""
操作审计日志服务

异步写入审计日志，写入失败不影响主业务流程。
"""
import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditEventType:
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SESSION_CREATE = "SESSION_CREATE"
    SESSION_CLOSE = "SESSION_CLOSE"
    TOKEN_VERIFY_FAIL = "TOKEN_VERIFY_FAIL"
    ADMIN_FORCE_LOGOUT = "ADMIN_FORCE_LOGOUT"
    ADMIN_UPDATE_WHITELIST = "ADMIN_UPDATE_WHITELIST"
    ADMIN_UPDATE_PERMISSIONS = "ADMIN_UPDATE_PERMISSIONS"
    NEW_DEVICE_LOGIN = "NEW_DEVICE_LOGIN"


class AuditService:

    def log(
        self,
        db: Session,
        event_type: str,
        user_id: Optional[int],
        username: Optional[str],
        client_ip: Optional[str],
        user_agent: Optional[str],
        event_detail: Optional[Dict[str, Any]],
        result: str,  # 'success' | 'failure'
    ) -> None:
        """
        写入审计日志。写入失败时记录到应用错误日志，不抛出异常。
        在 FastAPI 中通过 BackgroundTasks 异步执行，不阻塞主请求。
        """
        try:
            entry = AuditLog(
                event_type=event_type,
                user_id=user_id,
                username=username,
                client_ip=client_ip,
                user_agent=user_agent,
                event_time=datetime.utcnow(),
                event_detail=json.dumps(event_detail, ensure_ascii=False) if event_detail else None,
                result=result,
            )
            db.add(entry)
            db.commit()
        except Exception as e:
            logger.error(f"AuditService.log failed: {e}", exc_info=True)

    def query_logs(
        self,
        db: Session,
        filters: Dict[str, Any],
        limit: int = 100,
        offset: int = 0,
    ) -> tuple:
        """
        查询审计日志，支持 user_id / event_type / start_time / end_time 过滤。
        默认按时间倒序。
        """
        query = db.query(AuditLog)

        if filters.get("user_id"):
            query = query.filter(AuditLog.user_id == filters["user_id"])
        if filters.get("event_type"):
            query = query.filter(AuditLog.event_type == filters["event_type"])
        if filters.get("start_time"):
            query = query.filter(AuditLog.event_time >= filters["start_time"])
        if filters.get("end_time"):
            query = query.filter(AuditLog.event_time <= filters["end_time"])

        total = query.count()
        logs = (
            query.order_by(AuditLog.event_time.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return logs, total

    def export_csv(self, db: Session, filters: Dict[str, Any]) -> StreamingResponse:
        """流式导出 CSV，避免大数据量时内存溢出"""
        logs, _ = self.query_logs(db, filters, limit=100000, offset=0)

        def generate():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id", "event_type", "user_id", "username",
                "client_ip", "user_agent", "event_time", "event_detail", "result"
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            for log in logs:
                writer.writerow([
                    log.id, log.event_type, log.user_id, log.username,
                    log.client_ip, log.user_agent,
                    log.event_time.isoformat() if log.event_time else "",
                    log.event_detail or "",
                    log.result,
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = f"audit_logs_{date_str}.csv"
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
