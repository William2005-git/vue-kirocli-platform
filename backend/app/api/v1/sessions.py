from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    DailyQuotaExceededError,
    GottyStartupError,
    NoAvailablePortError,
    SessionLimitExceededError,
    SessionNotFoundError,
)
from app.models.user import User
from app.services.session_service import SessionService

router = APIRouter()


@router.post("/start")
async def start_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SessionService(db)
    try:
        session = await service.create_session(current_user.id)
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "gotty_url": session.gotty_url,
                "status": session.status,
                "started_at": session.started_at,
            },
        }
    except SessionLimitExceededError as e:
        raise HTTPException(status_code=403, detail={"code": e.code, "message": e.message})
    except DailyQuotaExceededError as e:
        raise HTTPException(status_code=403, detail={"code": e.code, "message": e.message})
    except (GottyStartupError, NoAvailablePortError) as e:
        raise HTTPException(status_code=500, detail={"code": e.code, "message": e.message})


@router.get("")
async def list_sessions(
    status: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SessionService(db)
    filter_user_id = None
    if current_user.role == "admin" and user_id is not None:
        filter_user_id = user_id
    elif current_user.role != "admin":
        filter_user_id = current_user.id

    sessions, total = service.get_sessions(
        user_id=filter_user_id, status=status, limit=limit, offset=offset
    )

    from app.models.user import User as UserModel
    session_list = []
    for sess in sessions:
        u = db.query(UserModel).filter_by(id=sess.user_id).first()
        session_list.append({
            "id": sess.id,
            "user_id": sess.user_id,
            "username": u.username if u else None,
            "gotty_url": sess.gotty_url,
            "status": sess.status,
            "started_at": sess.started_at,
            "last_activity_at": sess.last_activity_at,
            "duration_seconds": sess.duration_seconds,
        })

    return {
        "success": True,
        "data": {"sessions": session_list, "total": total, "limit": limit, "offset": offset},
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.session import Session as SessionModel
    from app.models.user import User as UserModel

    query = db.query(SessionModel).filter_by(id=session_id)
    if current_user.role != "admin":
        query = query.filter_by(user_id=current_user.id)
    sess = query.first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    u = db.query(UserModel).filter_by(id=sess.user_id).first()
    return {
        "success": True,
        "data": {
            "id": sess.id,
            "user_id": sess.user_id,
            "username": u.username if u else None,
            "gotty_url": sess.gotty_url,
            "gotty_pid": sess.gotty_pid,
            "gotty_port": sess.gotty_port,
            "status": sess.status,
            "started_at": sess.started_at,
            "last_activity_at": sess.last_activity_at,
            "duration_seconds": sess.duration_seconds,
        },
    }


@router.delete("/{session_id}")
async def close_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SessionService(db)
    try:
        await service.close_session(
            session_id, current_user.id, is_admin=(current_user.role == "admin")
        )
        return {"success": True, "message": "Session closed"}
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
