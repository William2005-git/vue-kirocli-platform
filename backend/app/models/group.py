from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Index("idx_user_groups_user_id", UserGroup.user_id)
Index("idx_user_groups_group_name", UserGroup.group_name)


class GroupRoleMapping(Base):
    __tablename__ = "group_role_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(100), unique=True, nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
