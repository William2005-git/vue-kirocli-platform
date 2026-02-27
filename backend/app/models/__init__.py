from app.models.user import User
from app.models.session import Session, AppSession
from app.models.permission import UserPermission
from app.models.preference import UserPreference
from app.models.group import UserGroup, GroupRoleMapping

# v1.1 新增模型
from app.models.ip_whitelist import IPWhitelist
from app.models.audit_log import AuditLog
from app.models.alert import AlertRule, AlertEvent
from app.models.token import RefreshToken, BlacklistedToken
from app.models.device import UserDevice
from app.models.system_config import SystemConfig

__all__ = [
    # v1.0
    "User",
    "Session",
    "AppSession",
    "UserPermission",
    "UserPreference",
    "UserGroup",
    "GroupRoleMapping",
    # v1.1
    "IPWhitelist",
    "AuditLog",
    "AlertRule",
    "AlertEvent",
    "RefreshToken",
    "BlacklistedToken",
    "UserDevice",
    "SystemConfig",
]
