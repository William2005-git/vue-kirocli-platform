import asyncio
import random
import string
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
from app.services.gotty_service import gotty_service


def _generate_session_id() -> str:
    chars = string.ascii_lowercase + string.digits
    return "sess_" + "".join(random.choices(chars, k=16))


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    async def create_session(self, user_id: int) -> SessionModel:
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

        asyncio.create_task(self._mark_running(session.id))
        return session

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
