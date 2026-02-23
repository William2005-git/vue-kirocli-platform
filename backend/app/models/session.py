from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gotty_pid = Column(Integer, nullable=False)
    gotty_port = Column(Integer, nullable=False)
    gotty_url = Column(String(512), nullable=False)
    random_token = Column(String(32), nullable=False)
    status = Column(String(20), nullable=False, default="starting")
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)


Index("idx_sessions_user_id", Session.user_id)
Index("idx_sessions_status", Session.status)
Index("idx_sessions_started_at", Session.started_at)
Index("idx_sessions_gotty_port", Session.gotty_port)


class AppSession(Base):
    __tablename__ = "app_sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Index("idx_app_sessions_user_id", AppSession.user_id)
Index("idx_app_sessions_expires_at", AppSession.expires_at)
