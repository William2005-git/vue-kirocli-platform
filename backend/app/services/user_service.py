from datetime import datetime
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import IAMSyncError, UserNotFoundError
from app.models.group import GroupRoleMapping, UserGroup
from app.models.permission import UserPermission
from app.models.preference import UserPreference
from app.models.session import Session as SessionModel
from app.models.user import User


def _create_default_permissions(db: Session, user_id: int):
    perm = UserPermission(user_id=user_id)
    db.add(perm)


def _create_default_preferences(db: Session, user_id: int):
    pref = UserPreference(user_id=user_id)
    db.add(pref)


def _resolve_group_display_name(group_id: str) -> str:
    """
    尝试通过 IAM Identity Store API 将 GroupId 解析为 DisplayName。
    失败时返回原始值（兼容直接使用 DisplayName 的场景）。
    """
    try:
        import boto3
        from app.config import settings
        if not settings.IAM_IDENTITY_STORE_ID or not settings.AWS_REGION:
            return group_id
        client = boto3.client("identitystore", region_name=settings.AWS_REGION)
        resp = client.describe_group(
            IdentityStoreId=settings.IAM_IDENTITY_STORE_ID,
            GroupId=group_id,
        )
        return resp.get("DisplayName", group_id)
    except Exception:
        return group_id


def _determine_role(db: Session, groups: List[str]) -> str:
    for group_id in groups:
        # 先直接匹配（兼容 DisplayName 直接存入的情况）
        mapping = db.query(GroupRoleMapping).filter_by(group_name=group_id).first()
        if not mapping:
            # 尝试将 GroupId 解析为 DisplayName 再匹配
            display_name = _resolve_group_display_name(group_id)
            if display_name != group_id:
                mapping = db.query(GroupRoleMapping).filter_by(group_name=display_name).first()
        if mapping and mapping.role == "admin":
            return "admin"
    return "user"


def _update_user_groups(db: Session, user: User, groups: List[str]):
    db.query(UserGroup).filter_by(user_id=user.id).delete()
    for g in groups:
        db.add(UserGroup(user_id=user.id, group_name=g))
    role = _determine_role(db, groups)
    user.role = role


def create_or_update_user(db: Session, user_info: dict) -> User:
    user = db.query(User).filter_by(username=user_info["username"]).first()
    if user:
        user.email = user_info.get("email", user.email)
        user.full_name = user_info.get("full_name", user.full_name)
        user.last_login_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
    else:
        user = User(
            username=user_info["username"],
            email=user_info.get("email", ""),
            full_name=user_info.get("full_name"),
            last_login_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()
        _create_default_permissions(db, user.id)
        _create_default_preferences(db, user.id)

    groups = user_info.get("groups", [])
    _update_user_groups(db, user, groups)
    db.commit()
    db.refresh(user)
    return user


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_groups(self, user_id: int) -> List[str]:
        groups = self.db.query(UserGroup).filter_by(user_id=user_id).all()
        return [g.group_name for g in groups]

    def get_user_permissions(self, user_id: int) -> Optional[UserPermission]:
        return self.db.query(UserPermission).filter_by(user_id=user_id).first()

    def get_user_preferences(self, user_id: int) -> Optional[UserPreference]:
        return self.db.query(UserPreference).filter_by(user_id=user_id).first()

    def update_permissions(self, user_id: int, data: dict):
        perm = self.db.query(UserPermission).filter_by(user_id=user_id).first()
        if not perm:
            raise UserNotFoundError()
        for k, v in data.items():
            if v is not None:
                setattr(perm, k, v)
        perm.updated_at = datetime.utcnow()
        self.db.commit()

    def update_preferences(self, user_id: int, data: dict):
        pref = self.db.query(UserPreference).filter_by(user_id=user_id).first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            self.db.add(pref)
        for k, v in data.items():
            if v is not None:
                setattr(pref, k, v)
        pref.updated_at = datetime.utcnow()
        self.db.commit()

    def get_user_total_sessions(self, user_id: int, today_only: bool = False) -> int:
        """
        获取用户会话数量
        
        Args:
            user_id: 用户 ID
            today_only: 是否只统计今天的会话（UTC 时间的"今天"）
        
        Returns:
            会话数量
        """
        query = self.db.query(SessionModel).filter_by(user_id=user_id)
        
        if today_only:
            # 计算 UTC 今天的开始时间（00:00:00）
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(SessionModel.started_at >= today_start)
        
        return query.count()

    def sync_from_iam(self) -> dict:
        if not settings.IAM_IDENTITY_STORE_ID:
            return {"synced_users": 0, "new_users": 0, "updated_users": 0, "synced_groups": 0}
        try:
            client = boto3.client("identitystore", region_name=settings.AWS_REGION)
            store_id = settings.IAM_IDENTITY_STORE_ID

            iam_users = []
            paginator = client.get_paginator("list_users")
            for page in paginator.paginate(IdentityStoreId=store_id):
                for u in page["Users"]:
                    emails = u.get("Emails", [])
                    email = emails[0].get("Value", "") if emails else ""
                    iam_users.append({
                        "iam_id": u["UserId"],
                        "username": u["UserName"],
                        "email": email,
                        "full_name": u.get("DisplayName", ""),
                        "status": "active" if u.get("Active", True) else "disabled",
                    })

            iam_groups = []
            gpaginator = client.get_paginator("list_groups")
            for page in gpaginator.paginate(IdentityStoreId=store_id):
                for g in page["Groups"]:
                    iam_groups.append({"id": g["GroupId"], "name": g["DisplayName"]})

            stats = {"synced_users": 0, "new_users": 0, "updated_users": 0, "synced_groups": len(iam_groups)}

            for iam_user in iam_users:
                user_groups = []
                try:
                    mp = client.get_paginator("list_group_memberships_for_member")
                    for page in mp.paginate(
                        IdentityStoreId=store_id,
                        MemberId={"UserId": iam_user["iam_id"]},
                    ):
                        for m in page["GroupMemberships"]:
                            grp = client.describe_group(
                                IdentityStoreId=store_id, GroupId=m["GroupId"]
                            )
                            user_groups.append(grp["DisplayName"])
                except ClientError:
                    pass

                existing = self.db.query(User).filter_by(username=iam_user["username"]).first()
                if existing:
                    existing.email = iam_user["email"]
                    existing.full_name = iam_user["full_name"]
                    existing.status = iam_user["status"]
                    _update_user_groups(self.db, existing, user_groups)
                    stats["updated_users"] += 1
                else:
                    new_user = User(
                        username=iam_user["username"],
                        email=iam_user["email"],
                        full_name=iam_user["full_name"],
                        status=iam_user["status"],
                    )
                    self.db.add(new_user)
                    self.db.flush()
                    _create_default_permissions(self.db, new_user.id)
                    _create_default_preferences(self.db, new_user.id)
                    _update_user_groups(self.db, new_user, user_groups)
                    stats["new_users"] += 1
                stats["synced_users"] += 1

            self.db.commit()
            return stats
        except ClientError as e:
            raise IAMSyncError(str(e))
