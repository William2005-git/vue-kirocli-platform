from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=True)
    username = Column(String(100), nullable=True)
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    event_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    event_detail = Column(Text, nullable=True)   # JSON 格式
    result = Column(String(20), nullable=False)  # 'success' / 'failure'


Index("idx_audit_logs_user_id", AuditLog.user_id)
Index("idx_audit_logs_event_type", AuditLog.event_type)
Index("idx_audit_logs_event_time", AuditLog.event_time)
