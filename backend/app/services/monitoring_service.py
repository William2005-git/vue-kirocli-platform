import csv
import io
from datetime import datetime, timedelta

import psutil
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.session import Session as SessionModel
from app.models.user import User


class MonitoringService:
    def __init__(self, db: Session):
        self.db = db

    def get_realtime_metrics(self) -> dict:
        active_sessions = (
            self.db.query(SessionModel).filter_by(status="running").count()
        )
        recent_threshold = datetime.utcnow() - timedelta(minutes=5)
        online_users = (
            self.db.query(SessionModel.user_id)
            .filter(
                SessionModel.status == "running",
                SessionModel.last_activity_at >= recent_threshold,
            )
            .distinct()
            .count()
        )
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory_usage = psutil.virtual_memory().percent
        return {
            "active_sessions": active_sessions,
            "online_users": online_users,
            "cpu_usage_percent": cpu_usage,
            "memory_usage_percent": memory_usage,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_statistics(self, days: int = 7) -> dict:
        start_date = datetime.utcnow() - timedelta(days=days)
        total_users = self.db.query(User).count()
        total_sessions = (
            self.db.query(SessionModel)
            .filter(SessionModel.started_at >= start_date)
            .count()
        )
        avg_duration = (
            self.db.query(func.avg(SessionModel.duration_seconds))
            .filter(
                SessionModel.started_at >= start_date,
                SessionModel.status == "closed",
            )
            .scalar()
            or 0
        )
        daily_sessions = (
            self.db.query(
                func.date(SessionModel.started_at).label("date"),
                func.count(SessionModel.id).label("count"),
            )
            .filter(SessionModel.started_at >= start_date)
            .group_by(func.date(SessionModel.started_at))
            .all()
        )
        top_users = (
            self.db.query(
                User.username,
                func.count(SessionModel.id).label("session_count"),
            )
            .join(SessionModel, User.id == SessionModel.user_id)
            .filter(SessionModel.started_at >= start_date)
            .group_by(User.username)
            .order_by(func.count(SessionModel.id).desc())
            .limit(10)
            .all()
        )
        return {
            "total_users": total_users,
            "total_sessions": total_sessions,
            "average_session_duration_seconds": int(avg_duration),
            "daily_sessions": [{"date": str(d.date), "count": d.count} for d in daily_sessions],
            "top_users": [{"username": u.username, "session_count": u.session_count} for u in top_users],
        }

    def export_csv(self, start_date: str, end_date: str) -> str:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            sd = datetime.utcnow() - timedelta(days=30)
            ed = datetime.utcnow()

        sessions = (
            self.db.query(SessionModel, User.username)
            .join(User, SessionModel.user_id == User.id)
            .filter(SessionModel.started_at >= sd, SessionModel.started_at < ed)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["session_id", "username", "status", "started_at", "closed_at", "duration_seconds"])
        for sess, username in sessions:
            writer.writerow([
                sess.id,
                username,
                sess.status,
                sess.started_at,
                sess.closed_at,
                sess.duration_seconds,
            ])
        return output.getvalue()
