"""
KiroCLI Platform v1.1 - 全新部署初始化脚本

适用场景：全新安装 v1.1，数据库文件不存在或为空。
执行方式：python scripts/init_db.py

会创建所有表（v1.0 + v1.1），并写入默认数据。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal, Base

# 导入所有模型，确保 Base 注册完整
from app.models import User, UserPermission, UserPreference
from app.models.group import GroupRoleMapping
# v1.1 新增模型
from app.models.ip_whitelist import IPWhitelist
from app.models.audit_log import AuditLog
from app.models.alert import AlertRule, AlertEvent
from app.models.token import RefreshToken, BlacklistedToken
from app.models.device import UserDevice
from app.models.system_config import SystemConfig


def seed_default_data(db):
    """写入预置数据（幂等，已存在则跳过）"""

    # v1.0：组角色映射
    for group_name, role in [("KiroCLI-Admins", "admin"), ("KiroCLI-Users", "user")]:
        if not db.query(GroupRoleMapping).filter_by(group_name=group_name).first():
            db.add(GroupRoleMapping(group_name=group_name, role=role))
            print(f"  Created group mapping: {group_name} -> {role}")

    # v1.0：默认管理员用户
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@example.com",
            full_name="Default Admin",
            role="admin",
            status="active",
        )
        db.add(admin)
        db.flush()
        db.add(UserPermission(
            user_id=admin.id,
            max_concurrent_sessions=10,
            max_session_duration_hours=8,
            daily_session_quota=50,
            can_start_terminal=True,
            can_view_monitoring=True,
            can_export_data=True,
        ))
        db.add(UserPreference(user_id=admin.id))
        print("  Created default admin user (username: admin)")

    # v1.1：告警规则默认配置
    default_rules = [
        ("session_burst",  "会话创建频率异常", 10, 5),
        ("login_failure",  "登录失败次数异常", 5,  10),
        ("multi_ip_login", "多IP登录异常",     60, 3),
        ("offhour_login",  "非工作时间登录",   0,  0),
    ]
    for rule_key, rule_name, window, threshold in default_rules:
        if not db.query(AlertRule).filter_by(rule_key=rule_key).first():
            db.add(AlertRule(
                rule_key=rule_key,
                rule_name=rule_name,
                time_window_minutes=window,
                threshold=threshold,
            ))
            print(f"  Created alert rule: {rule_key}")

    # v1.1：系统配置默认值
    default_configs = [
        ("ip_whitelist_enabled",   "false"),
        ("alert_offhour_start",    "22:00"),
        ("alert_offhour_end",      "08:00"),
        ("alert_offhour_tz",       "Asia/Shanghai"),
        ("alert_cooldown_minutes", "30"),
        ("sns_topic_arn",          ""),
        ("secret_key_hash",        ""),
    ]
    for key, value in default_configs:
        if not db.query(SystemConfig).filter_by(key=key).first():
            db.add(SystemConfig(key=key, value=value))
            print(f"  Created system config: {key}")

    db.commit()


def init():
    print("=== KiroCLI Platform v1.1 - 全新部署初始化 ===")
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db = SessionLocal()
    try:
        print("Seeding default data...")
        seed_default_data(db)
        print("Initialization complete.")
    finally:
        db.close()


if __name__ == "__main__":
    init()
