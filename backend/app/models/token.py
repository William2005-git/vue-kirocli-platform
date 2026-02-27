from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False)  # SHA-256(plaintext)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Index("idx_refresh_tokens_user_id", RefreshToken.user_id)
Index("idx_refresh_tokens_token_hash", RefreshToken.token_hash)
Index("idx_refresh_tokens_expires_at", RefreshToken.expires_at)


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_jti = Column(String(128), unique=True, nullable=False)  # JWT jti claim
    user_id = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)   # 原 JWT 过期时间，用于自动清理
    blacklisted_at = Column(DateTime, default=datetime.utcnow)


Index("idx_blacklisted_tokens_jti", BlacklistedToken.token_jti)
Index("idx_blacklisted_tokens_expires_at", BlacklistedToken.expires_at)
