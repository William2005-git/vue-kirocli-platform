"""Database initialization script - creates tables and seeds default data."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal, Base
from app.models import User, UserPermission, UserPreference
from app.models.group import GroupRoleMapping


def init():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db = SessionLocal()
    try:
        for group_name, role in [("KiroCLI-Admins", "admin"), ("KiroCLI-Users", "user")]:
            existing = db.query(GroupRoleMapping).filter_by(group_name=group_name).first()
            if not existing:
                db.add(GroupRoleMapping(group_name=group_name, role=role))
                print(f"Created group mapping: {group_name} -> {role}")

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
            print("Created default admin user (username: admin)")

        db.commit()
        print("Database initialization complete.")
    finally:
        db.close()


if __name__ == "__main__":
    init()
