import asyncio
import logging
import random
import string
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import (
    DailyQuotaExceededError,
    SessionLimitExceededError,
    SessionNotFoundError,
)
from app.models.permission import UserPermission
from app.models.session import Session as SessionModel
from app.services.audit_service import AuditEventType, AuditService
from app.services.gotty_service import gotty_service

logger = logging.getLogger(__name__)

NGINX_GOTTY_ROUTES_CONF = "/etc/nginx/conf.d/gotty_routes.conf"
_audit_service = AuditService()

# 延迟导入避免循环依赖
def _get_alert_service():
    from app.core.database import SessionLocal
    from app.services.alert_service import AlertService
    return AlertService(SessionLocal)


def _generate_session_id() -> str:
    chars = string.ascii_lowercase + string.digits
    return "sess_" + "".join(random.choices(chars, k=16))


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    async def create_session(self, user_id: int, client_ip: str = None, username: str = None) -> SessionModel:
        await self._check_concurrent_limit(user_id)
        await self._check_daily_quota(user_id)

        gotty_sess = await gotty_service.start_gotty(user_id)

        session = SessionModel(
            id=_generate_session_id(),
            user_id=user_id,
            gotty_pid=gotty_sess.pid,
            gotty_port=gotty_sess.port,
            gotty_url=gotty_sess.url,
            random_token=gotty_sess.token,
            status="starting",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # 审计日志：会话创建
        _audit_service.log(
            self.db, AuditEventType.SESSION_CREATE,
            user_id, username, client_ip, None,
            {"session_id": session.id, "gotty_port": gotty_sess.port}, "success"
        )

        asyncio.create_task(self._mark_running(session.id))
        # 更新 Nginx Gotty 路由（异步，不阻塞会话创建响应）
        asyncio.create_task(self._update_gotty_routes_async())
        # 告警检测：会话创建频率
        asyncio.create_task(self._check_session_alert(user_id, client_ip, username))
        return session

    async def _check_session_alert(self, user_id: int, client_ip: str = None, username: str = None):
        """异步触发会话创建告警检测"""
        try:
            alert_service = _get_alert_service()
            await alert_service.check_and_alert(AuditEventType.SESSION_CREATE, user_id, client_ip, None, username)
        except Exception as e:
            logger.warning(f"Session alert check failed: {e}")

    async def _mark_running(self, session_id: str):
        await asyncio.sleep(2)
        db = next(self._get_db())
        try:
            sess = db.query(SessionModel).filter_by(id=session_id).first()
            if sess and sess.status == "starting":
                sess.status = "running"
                db.commit()
        finally:
            db.close()

    def _get_db(self):
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def close_session(self, session_id: str, user_id: int, is_admin: bool = False):
        query = self.db.query(SessionModel).filter_by(id=session_id)
        if not is_admin:
            query = query.filter_by(user_id=user_id)
        session = query.first()
        if not session:
            raise SessionNotFoundError()

        await gotty_service.stop_gotty(session.gotty_pid, session.gotty_port)

        now = datetime.utcnow()
        session.status = "closed"
        session.closed_at = now
        if session.started_at:
            session.duration_seconds = int((now - session.started_at).total_seconds())
        self.db.commit()

        # 审计日志：会话关闭
        _audit_service.log(
            self.db, AuditEventType.SESSION_CLOSE,
            session.user_id, None, None, None,
            {"session_id": session.id, "duration_seconds": session.duration_seconds}, "success"
        )

        # 更新 Nginx Gotty 路由
        self._update_gotty_routes()

    async def cleanup_idle_sessions(self):
        threshold = datetime.utcnow() - timedelta(
            minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES
        )
        idle = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.status == "running",
                SessionModel.last_activity_at < threshold,
            )
            .all()
        )
        for sess in idle:
            try:
                await self.close_session(sess.id, sess.user_id, is_admin=True)
            except Exception:
                pass

    async def restore_sessions_on_startup(self):
        active = (
            self.db.query(SessionModel)
            .filter(SessionModel.status.in_(["starting", "running"]))
            .all()
        )
        for sess in active:
            alive = await gotty_service.check_process_alive(sess.gotty_pid)
            if not alive:
                sess.status = "closed"
                sess.closed_at = datetime.utcnow()
            else:
                sess.status = "running"
        self.db.commit()

    async def _check_concurrent_limit(self, user_id: int):
        perm = self.db.query(UserPermission).filter_by(user_id=user_id).first()
        max_sessions = perm.max_concurrent_sessions if perm else 3
        current = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.status.in_(["starting", "running"]),
            )
            .count()
        )
        if current >= max_sessions:
            raise SessionLimitExceededError(current, max_sessions)

    async def _check_daily_quota(self, user_id: int):
        perm = self.db.query(UserPermission).filter_by(user_id=user_id).first()
        quota = perm.daily_session_quota if perm else 10
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.started_at >= today_start,
            )
            .count()
        )
        if count >= quota:
            raise DailyQuotaExceededError()

    def get_sessions(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple:
        query = self.db.query(SessionModel)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        total = query.count()
        sessions = query.order_by(SessionModel.started_at.desc()).offset(offset).limit(limit).all()
        return sessions, total

    def _update_gotty_routes(self) -> None:
        """
        查询所有 running 状态的会话，生成 Nginx Gotty 路由配置并 reload。
        同步版本，在会话关闭时调用。
        """
        try:
            active = (
                self.db.query(SessionModel)
                .filter(SessionModel.status.in_(["starting", "running"]))
                .all()
            )
            conf = _generate_gotty_routes_conf(active)
            with open(NGINX_GOTTY_ROUTES_CONF, "w") as f:
                f.write(conf)
            subprocess.run(
                ["/usr/bin/sudo", "/usr/sbin/nginx", "-s", "reload"],
                capture_output=True, text=True, timeout=10, check=False
            )
        except Exception as e:
            logger.warning(f"Failed to update Gotty routes: {e}")

    async def _update_gotty_routes_async(self) -> None:
        """异步版本，在会话创建后调用（等待 Gotty 启动后再更新路由）"""
        await asyncio.sleep(3)
        self._update_gotty_routes()


def _generate_gotty_routes_conf(sessions: list) -> str:
    """
    生成 token → port 的 map 映射配置。
    使用单个通用 location 块处理所有 /terminal/ 请求，通过 map 动态路由到对应端口。
    这样避免了时序问题：前端可以立即打开终端 URL，无需等待 Nginx 配置更新。
    """
    lines = [
        "# 由 KiroCLI Platform 自动生成，请勿手动修改",
        f"# 更新时间: {datetime.utcnow().isoformat()}Z",
        "",
        "# Token 到 Gotty 端口的映射",
        "map $session_token_var $gotty_backend_port {",
        "    default 0;",
    ]
    
    for sess in sessions:
        token = sess.random_token
        port = sess.gotty_port
        lines.append(f"    {token} {port};")
    
    lines += [
        "}",
        "",
    ]
    
    return "\n".join(lines)
