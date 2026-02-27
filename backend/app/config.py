from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "KiroCLI Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-to-a-random-secret-key"

    DATABASE_URL: str = "sqlite:///./data.db"

    SAML_IDP_ENTITY_ID: Optional[str] = None
    SAML_IDP_SSO_URL: Optional[str] = None
    SAML_IDP_X509_CERT: Optional[str] = None
    SAML_SP_ENTITY_ID: Optional[str] = None
    SAML_SP_ACS_URL: Optional[str] = None
    SAML_SP_PRIVATE_KEY: Optional[str] = None

    IAM_IDENTITY_STORE_ID: str = ""
    AWS_REGION: str = "us-east-1"

    GOTTY_PRIMARY_PORT: int = 7860
    GOTTY_PORT_START: int = 7861
    GOTTY_PORT_END: int = 7960
    GOTTY_CERT_PATH: Optional[str] = None
    GOTTY_KEY_PATH: Optional[str] = None
    GOTTY_PATH: str = "/usr/local/bin/gotty"
    KIRO_CLI_PATH: str = "kiro-cli"
    GOTTY_REMOTE_MODE: bool = False
    GOTTY_REMOTE_HOST: Optional[str] = None

    SSH_HOST: str = ""
    SSH_PORT: int = 22
    SSH_USER: str = "ubuntu"
    SSH_KEY_PATH: str = ""
    SSH_REMOTE_HOME: str = "/home/ubuntu"

    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    DOMAIN: Optional[str] = None

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/kirocli-platform/backend.log"

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 8

    SESSION_IDLE_TIMEOUT_MINUTES: int = 30
    SESSION_CLEANUP_INTERVAL_MINUTES: int = 5

    # AWS Secrets Manager
    SECRETS_MANAGER_ENABLED: bool = False
    SECRETS_MANAGER_SECRET_NAME: str = "kirocli-platform/development"
    SECRETS_MANAGER_FALLBACK_TO_ENV: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# 若启用 Secrets Manager，覆盖敏感配置项
if settings.SECRETS_MANAGER_ENABLED:
    try:
        from app.services.secrets_manager import secrets_loader, _load_sources
        _secrets = secrets_loader.load(
            settings.SECRETS_MANAGER_SECRET_NAME,
            fallback_to_env=settings.SECRETS_MANAGER_FALLBACK_TO_ENV,
        )
        _OVERRIDABLE = ("SECRET_KEY", "SAML_IDP_X509_CERT", "SAML_SP_PRIVATE_KEY")
        for _key in _OVERRIDABLE:
            if _key in _secrets:
                object.__setattr__(settings, _key, _secrets[_key])
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"Secrets Manager override failed: {_e}")
