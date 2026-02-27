"""
AWS Secrets Manager 集成

启动时一次性加载密钥，支持密钥轮换检测。
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 记录各配置项的加载来源
_load_sources: dict = {}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class SecretsManagerLoader:
    def load(self, secret_name: str, fallback_to_env: bool = True) -> dict:
        """
        从 AWS Secrets Manager 加载密钥，返回解析后的 dict。
        失败时根据 fallback_to_env 决定回退（返回空 dict）或抛出异常。
        """
        try:
            import boto3
            from app.config import settings
            client = boto3.client(
                "secretsmanager",
                region_name=settings.AWS_REGION or None,
            )
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response.get("SecretString", "{}")
            secrets = json.loads(secret_string)
            logger.info(f"Loaded {len(secrets)} secrets from Secrets Manager: {secret_name}")
            for key in secrets:
                _load_sources[key] = "secrets_manager"
            return secrets
        except Exception as e:
            if fallback_to_env:
                logger.warning(f"Secrets Manager load failed, falling back to env: {e}")
                return {}
            raise RuntimeError(f"Failed to load secrets from Secrets Manager: {e}") from e

    def check_key_rotation(self, db, current_secret_key: str) -> bool:
        """
        检测 SECRET_KEY 是否已轮换。
        比对当前 key 的 SHA-256 与 system_config 中存储的哈希。
        不一致时撤销所有 Refresh Token 并更新 system_config。
        返回 True 表示检测到轮换。
        """
        from app.models.system_config import SystemConfig
        from app.services.token_service import token_service

        current_hash = _sha256(current_secret_key)
        cfg = db.query(SystemConfig).filter_by(key="secret_key_hash").first()

        if cfg is None:
            # 首次启动，写入哈希
            db.add(SystemConfig(key="secret_key_hash", value=current_hash, updated_at=datetime.utcnow()))
            db.commit()
            logger.info("secret_key_hash initialized in system_config")
            return False

        if cfg.value != current_hash:
            logger.warning("SECRET_KEY rotation detected, revoking all refresh tokens")
            # 撤销所有用户的 Refresh Token
            from app.models.token import RefreshToken
            db.query(RefreshToken).filter_by(revoked=False).update({"revoked": True})
            cfg.value = current_hash
            cfg.updated_at = datetime.utcnow()
            db.commit()
            # 重新初始化黑名单缓存
            token_service.init_blacklist_cache(db)
            return True

        return False

    def get_load_sources(self) -> dict:
        """返回各配置项的加载来源"""
        return dict(_load_sources)


secrets_loader = SecretsManagerLoader()
