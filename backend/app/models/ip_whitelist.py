from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class IPWhitelist(Base):
    __tablename__ = "ip_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cidr = Column(String(50), nullable=False)
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
