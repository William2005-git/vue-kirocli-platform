from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import require_admin
from app.core.database import get_db
from app.models.group import GroupRoleMapping, UserGroup
from app.models.permission import UserPermission
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.user_service import UserService

router = APIRouter()


@router.post("/users/sync")
async def sync_users(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    try:
        stats = service.sync_from_iam()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    total = query.count()
    users = query.offset(offset).limit(limit).all()

    service = UserService(db)
    user_list = []
    for u in users:
        user_list.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "status": u.status,
            "last_login_at": u.last_login_at,
            "total_sessions": service.get_user_total_sessions(u.id),
        })

    return {"success": True, "data": {"users": user_list, "total": total, "limit": limit, "offset": offset}}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = UserService(db)
    groups = service.get_user_groups(user_id)
    perm = service.get_user_permissions(user_id)
    total_sessions = service.get_user_total_sessions(user_id)

    recent_sessions = (
        db.query(SessionModel)
        .filter_by(user_id=user_id)
        .order_by(SessionModel.started_at.desc())
        .limit(5)
        .all()
    )

    permissions = {}
    if perm:
        permissions = {
            "max_concurrent_sessions": perm.max_concurrent_sessions,
            "max_session_duration_hours": perm.max_session_duration_hours,
            "daily_session_quota": perm.daily_session_quota,
            "can_start_terminal": perm.can_start_terminal,
            "can_view_monitoring": perm.can_view_monitoring,
            "can_export_data": perm.can_export_data,
        }

    return {
        "success": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
            "groups": groups,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "permissions": permissions,
            "statistics": {
                "total_sessions": total_sessions,
                "recent_sessions": [
                    {"id": s.id, "started_at": s.started_at, "duration_seconds": s.duration_seconds}
                    for s in recent_sessions
                ],
            },
        },
    }


@router.put("/users/{user_id}/permissions")
async def update_permissions(
    user_id: int,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    try:
        service.update_permissions(user_id, body)
        return {"success": True, "message": "Permissions updated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/groups")
async def list_groups(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    mappings = db.query(GroupRoleMapping).all()
    groups = []
    for m in mappings:
        member_count = db.query(UserGroup).filter_by(group_name=m.group_name).count()
        groups.append({
            "id": m.id,
            "group_name": m.group_name,
            "role": m.role,
            "member_count": member_count,
        })
    return {"success": True, "data": {"groups": groups}}


@router.put("/groups/{group_id}/role")
async def update_group_role(
    group_id: int,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    mapping = db.query(GroupRoleMapping).filter_by(id=group_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Group not found")
    role = body.get("role")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role")
    mapping.role = role
    db.commit()
    return {"success": True, "message": "Group role updated"}
