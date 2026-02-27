"""
JWT Refresh Token 服务

管理 Refresh Token 的生成、验证、轮换和黑名单。
内存缓存黑名单 jti，减少数据库查询。
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

from sqlalchemy.orm import Session

from app.models.token import BlacklistedToken, RefreshToken

logger = logging.getLogger(__name__)

REFRESH_TOKEN_EXPIRE_DAYS = 7


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class TokenService:
    def __init__(self):
        # 内存黑名单缓存（jti set）
        self._blacklist: Set[str] = set()
        self._initialized = False

    def init_blacklist_cache(self, db: Session) -> None:
        """启动时从数据库加载所有未过期的 jti 到内存"""
        now = datetime.utcnow()
        rows = db.query(BlacklistedToken.token_jti).filter(
            BlacklistedToken.expires_at > now
        ).all()
        self._blacklist = {r.token_jti for r in rows}
        self._initialized = True
        logger.info(f"Blacklist cache initialized with {len(self._blacklist)} entries")

    def create_refresh_token(self, db: Session, user_id: int) -> str:
        """生成 Refresh Token，存储哈希，返回明文"""
        plaintext = secrets.token_urlsafe(32)
        token_hash = _sha256(plaintext)
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        db.add(RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        ))
        db.commit()
        return plaintext

    def verify_refresh_token(self, db: Session, token_plaintext: str) -> Optional[int]:
        """验证 Refresh Token，返回 user_id 或 None"""
        token_hash = _sha256(token_plaintext)
        rt = db.query(RefreshToken).filter_by(token_hash=token_hash, revoked=False).first()
        if not rt:
            return None
        if rt.expires_at < datetime.utcnow():
            return None
        return rt.user_id

    def rotate_refresh_token(self, db: Session, old_token_plaintext: str) -> Optional[str]:
        """撤销旧 token，创建新 token，返回新明文；旧 token 无效时返回 None"""
        token_hash = _sha256(old_token_plaintext)
        rt = db.query(RefreshToken).filter_by(token_hash=token_hash, revoked=False).first()
        if not rt or rt.expires_at < datetime.utcnow():
            return None
        user_id = rt.user_id
        rt.revoked = True
        db.commit()
        return self.create_refresh_token(db, user_id)

    def revoke_all_user_tokens(self, db: Session, user_id: int) -> None:
        """撤销用户所有 Refresh Token"""
        db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).update({"revoked": True})
        db.commit()

    def blacklist_access_token(self, db: Session, jti: str, user_id: int, expires_at: datetime) -> None:
        """将 Access Token jti 加入黑名单（数据库 + 内存缓存）"""
        existing = db.query(BlacklistedToken).filter_by(token_jti=jti).first()
        if not existing:
            db.add(BlacklistedToken(
                token_jti=jti,
                user_id=user_id,
                expires_at=expires_at,
                blacklisted_at=datetime.utcnow(),
            ))
            db.commit()
        self._blacklist.add(jti)

    def is_blacklisted(self, jti: str, db: Optional[Session] = None) -> bool:
        """先查内存缓存，未命中再查数据库"""
        if jti in self._blacklist:
            return True
        if db is not None:
            row = db.query(BlacklistedToken).filter_by(token_jti=jti).first()
            if row:
                self._blacklist.add(jti)
                return True
        return False

    def cleanup_expired(self, db: Session) -> None:
        """清理已过期的 refresh_tokens 和 blacklisted_tokens"""
        now = datetime.utcnow()
        deleted_rt = db.query(RefreshToken).filter(RefreshToken.expires_at < now).delete()
        deleted_bt = db.query(BlacklistedToken).filter(BlacklistedToken.expires_at < now).delete()
        db.commit()
        # 同步清理内存缓存（重新加载）
        self.init_blacklist_cache(db)
        logger.info(f"Cleanup: removed {deleted_rt} refresh tokens, {deleted_bt} blacklisted tokens")


# 全局单例
token_service = TokenService()
