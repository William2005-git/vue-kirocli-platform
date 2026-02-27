from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.core.database import Base


class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fingerprint_hash = Column(String(128), nullable=False)  # SHA-256(browser_features)
    device_name = Column(String(100), nullable=True)        # 用户自定义，默认为 UA 摘要
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_ip = Column(String(50), nullable=True)
    login_count = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint_hash", name="uq_user_device_fingerprint"),
    )


Index("idx_user_devices_user_id", UserDevice.user_id)
Index("idx_user_devices_fingerprint", UserDevice.fingerprint_hash)
