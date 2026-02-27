from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
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
from app.core.security import decode_access_token
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.audit_service import AuditEventType, AuditService
from app.services.session_service import SessionService

router = APIRouter()
_audit_service = AuditService()


@router.get("/token-verify")
async def token_verify(
    request: Request,
    background_tasks: BackgroundTasks,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
):
    """
    供 Nginx auth_request 调用的 Token 绑定验证接口。
    从 Cookie 读取 JWT，从请求头 X-Session-Token 读取 session_token，
    验证两者绑定关系。
    """
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else ""
    )

    # 1. 读取 JWT Cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.TOKEN_VERIFY_FAIL,
            None, None, client_ip, request.headers.get("User-Agent"),
            {"reason": "missing_jwt_cookie", "path": str(request.url)}, "failure"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing JWT cookie")

    # 2. 验证 JWT
    payload = decode_access_token(access_token)
    if payload is None:
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.TOKEN_VERIFY_FAIL,
            None, None, client_ip, request.headers.get("User-Agent"),
            {"reason": "invalid_jwt", "path": str(request.url)}, "failure"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired JWT")

    jwt_user_id = payload.get("sub")
    if jwt_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT payload")

    # 3. 验证 session_token 存在
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing session token")

    # 4. 查找会话
    session = db.query(SessionModel).filter_by(random_token=x_session_token).first()
    if not session:
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.TOKEN_VERIFY_FAIL,
            int(jwt_user_id), None, client_ip, request.headers.get("User-Agent"),
            {"reason": "session_not_found", "session_token": x_session_token}, "failure"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not found")

    # 5. 检查会话状态
    if session.status == "closed":
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.TOKEN_VERIFY_FAIL,
            int(jwt_user_id), None, client_ip, request.headers.get("User-Agent"),
            {"reason": "session_closed", "session_id": session.id}, "failure"
        )
        raise HTTPException(status_code=410, detail="Session already closed")

    if session.status not in ("running", "starting"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not active")
    # 6. 验证用户归属
    if str(session.user_id) != str(jwt_user_id):
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.TOKEN_VERIFY_FAIL,
            int(jwt_user_id), None, client_ip, request.headers.get("User-Agent"),
            {
                "reason": "user_mismatch",
                "jwt_user_id": jwt_user_id,
                "session_user_id": session.user_id,
            },
            "failure"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User mismatch")

    return {"success": True}


@router.post("/start")
async def start_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SessionService(db)
    try:
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"
        session = await service.create_session(current_user.id, client_ip, current_user.username)
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "gotty_url": session.gotty_url,
                "random_token": session.random_token,
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
            "random_token": sess.random_token,
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
            "random_token": sess.random_token,
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
