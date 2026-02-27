from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from app.core.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_key = Column(String(100), unique=True, nullable=False)
    rule_name = Column(String(200), nullable=False)
    time_window_minutes = Column(Integer, nullable=False, default=0)
    threshold = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_key = Column(String(100), nullable=False)
    triggered_user_id = Column(Integer, nullable=True)
    triggered_username = Column(String(100), nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    event_detail = Column(Text, nullable=True)          # JSON
    notification_sent = Column(Boolean, default=False, nullable=False)
    notification_error = Column(Text, nullable=True)


Index("idx_alert_events_rule_key", AlertEvent.rule_key)
Index("idx_alert_events_triggered_at", AlertEvent.triggered_at)
Index("idx_alert_events_user_id", AlertEvent.triggered_user_id)
