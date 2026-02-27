"""
KiroCLI Platform v1.1 - 从 v1.0 升级脚本

适用场景：已有 v1.0 运行中的数据库，升级到 v1.1。
执行方式：python scripts/upgrade_db.py

操作内容：
  1. 检测 v1.0 数据库是否存在（通过 users 表判断）
  2. 新增 v1.1 的 8 张表（create_all 幂等，已存在的表跳过）
  3. 写入 v1.1 预置数据（告警规则、系统配置默认值）
  4. 不修改、不删除任何 v1.0 现有表和数据
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from app.core.database import engine, SessionLocal, Base

# 导入 v1.0 模型（确保 Base 注册，create_all 时不会误删）
from app.models import User, UserPermission, UserPreference
from app.models.group import GroupRoleMapping

# 导入 v1.1 新增模型
from app.models.ip_whitelist import IPWhitelist
from app.models.audit_log import AuditLog
from app.models.alert import AlertRule, AlertEvent
from app.models.token import RefreshToken, BlacklistedToken
from app.models.device import UserDevice
from app.models.system_config import SystemConfig

V11_NEW_TABLES = [
    "ip_whitelist",
    "audit_logs",
    "alert_rules",
    "alert_events",
    "refresh_tokens",
    "blacklisted_tokens",
    "user_devices",
    "system_config",
]


def check_v10_exists():
    """确认 v1.0 数据库存在（users 表必须存在）"""
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    if "users" not in existing:
        print("ERROR: 未检测到 v1.0 数据库（users 表不存在）。")
        print("       如需全新部署，请运行 init_db.py。")
        sys.exit(1)
    return existing


def create_new_tables(existing_tables):
    """只创建 v1.1 新增的表，跳过已存在的"""
    missing = [t for t in V11_NEW_TABLES if t not in existing_tables]
    if not missing:
        print("所有 v1.1 新表已存在，无需创建。")
        return

    print(f"需要创建的新表：{missing}")
    Base.metadata.create_all(bind=engine)
    print("新表创建完成。")


def seed_v11_data(db):
    """写入 v1.1 预置数据（幂等）"""

    # 告警规则默认配置
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
        else:
            print(f"  Alert rule already exists, skipped: {rule_key}")

    # 系统配置默认值
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
        else:
            print(f"  System config already exists, skipped: {key}")

    db.commit()


def upgrade():
    print("=== KiroCLI Platform v1.1 - 从 v1.0 升级 ===")

    print("\n[1/3] 检查 v1.0 数据库...")
    existing_tables = check_v10_exists()
    print(f"  检测到现有表：{existing_tables}")

    print("\n[2/3] 创建 v1.1 新增表...")
    create_new_tables(existing_tables)

    print("\n[3/3] 写入 v1.1 预置数据...")
    db = SessionLocal()
    try:
        seed_v11_data(db)
    finally:
        db.close()

    print("\n=== 升级完成 ===")
    print("v1.0 数据完整保留，v1.1 新功能表已就绪。")
    print("请重启 Backend 服务使配置生效。")


if __name__ == "__main__":
    upgrade()
