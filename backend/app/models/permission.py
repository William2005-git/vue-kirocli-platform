from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer

from app.core.database import Base


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    max_concurrent_sessions = Column(Integer, default=3)
    max_session_duration_hours = Column(Integer, default=2)
    daily_session_quota = Column(Integer, default=10)
    can_start_terminal = Column(Boolean, default=True)
    can_view_monitoring = Column(Boolean, default=True)
    can_export_data = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Index("idx_user_permissions_user_id", UserPermission.user_id)
