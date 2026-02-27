import logging
import secrets
import time
from datetime import timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import SAMLError
from app.core.saml import get_saml_settings, is_saml_configured, parse_saml_attributes
from app.core.security import create_access_token, decode_access_token
from app.models.session import Session as SessionModel
from app.core.database import SessionLocal
from app.services.alert_service import AlertService
from app.services.audit_service import AuditEventType, AuditService
from app.services.device_service import device_service
from app.services.gotty_service import gotty_service
from app.services.token_service import token_service
from app.services.user_service import create_or_update_user

router = APIRouter()
_audit_service = AuditService()
_alert_service = AlertService(SessionLocal)

# 服务端短期存储：state_id -> (fingerprint, expire_ts)
# AWS IAM Identity Center 会覆盖 RelayState，改用 cookie 传递 state_id
_saml_state: Dict[str, Tuple[str, float]] = {}
_STATE_TTL = 300  # 5 分钟


def _store_saml_state(fingerprint: str) -> str:
    """存储指纹，返回 state_id"""
    state_id = secrets.token_urlsafe(16)
    _saml_state[state_id] = (fingerprint, time.time() + _STATE_TTL)
    # 顺便清理过期条目
    now = time.time()
    expired = [k for k, (_, exp) in _saml_state.items() if exp < now]
    for k in expired:
        _saml_state.pop(k, None)
    return state_id


def _pop_saml_state(state_id: str) -> str:
    """取出并删除指纹，过期或不存在返回空字符串"""
    if not state_id:
        return ""
    entry = _saml_state.pop(state_id, None)
    if not entry:
        return ""
    fingerprint, exp = entry
    if time.time() > exp:
        return ""
    return fingerprint


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


@router.get("/saml/login")
async def saml_login(request: Request):
    if not is_saml_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SAML_NOT_CONFIGURED", "message": "SAML is not configured"},
        )
    try:
        from urllib.parse import urlparse
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        saml_settings = get_saml_settings()
        parsed = urlparse(settings.SAML_SP_ACS_URL)
        is_https = parsed.scheme == "https"
        port = parsed.port or (443 if is_https else 80)
        req = {
            "https": "on" if is_https else "off",
            "http_host": f"{parsed.hostname}:{port}",
            "script_name": "/",
            "server_port": str(port),
            "get_data": {},
            "post_data": {},
        }
        auth = OneLogin_Saml2_Auth(req, saml_settings)
        # 将设备指纹存入服务端 state，通过 cookie 传递（AWS IAM Identity Center 会覆盖 RelayState）
        fingerprint = request.query_params.get("fingerprint", "")
        login_url = auth.login()
        redirect = RedirectResponse(url=login_url)
        if fingerprint:
            state_id = _store_saml_state(fingerprint)
            redirect.set_cookie(
                key="saml_state",
                value=state_id,
                httponly=True,
                samesite="lax",
                max_age=_STATE_TTL,
            )
        return redirect
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/saml/callback")
async def saml_callback(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not is_saml_configured():
        raise HTTPException(status_code=503, detail="SAML not configured")
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    try:
        from urllib.parse import urlparse
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        form_data = await request.form()
        saml_response = form_data.get("SAMLResponse", "")
        saml_settings = get_saml_settings()
        parsed = urlparse(settings.SAML_SP_ACS_URL)
        is_https = parsed.scheme == "https"
        port = parsed.port or (443 if is_https else 80)
        req = {
            "https": "on" if is_https else "off",
            "http_host": f"{parsed.hostname}:{port}",
            "script_name": parsed.path,
            "server_port": str(port),
            "get_data": dict(request.query_params),
            "post_data": {"SAMLResponse": saml_response},
        }
        auth = OneLogin_Saml2_Auth(req, saml_settings)
        auth.process_response()
        errors = auth.get_errors()
        if errors:
            raise SAMLError(f"SAML errors: {errors}")

        attributes = auth.get_attributes()
        name_id = auth.get_nameid()
        user_info = parse_saml_attributes(attributes)
        if not user_info["username"] and name_id:
            user_info["username"] = name_id
        if not user_info["email"] and "@" in (name_id or ""):
            user_info["email"] = name_id

        user = create_or_update_user(db, user_info)
        # 从 saml_state cookie 取回设备指纹（AWS IAM Identity Center 会覆盖 RelayState，改用服务端 state）
        state_id = request.cookies.get("saml_state", "")
        fingerprint_hash = _pop_saml_state(state_id)
        if not fingerprint_hash:
            fingerprint_hash = request.headers.get("X-Device-Fingerprint", "")
        is_new_device = device_service.process_login(db, user.id, fingerprint_hash, client_ip, user_agent)

        token = create_access_token(
            {"sub": str(user.id)},
            expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        )
        refresh_token_plaintext = token_service.create_refresh_token(db, user.id)

        # 审计日志：登录成功
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.LOGIN,
            user.id, user.username, client_ip, user_agent,
            {"method": "saml"}, "success"
        )
        # 告警检测：登录成功
        background_tasks.add_task(
            _alert_service.check_and_alert,
            AuditEventType.LOGIN, user.id, client_ip, None, user.username,
        )
        # 新设备登录审计
        if is_new_device:
            background_tasks.add_task(
                _audit_service.log, db, AuditEventType.NEW_DEVICE_LOGIN,
                user.id, user.username, client_ip, user_agent,
                {"fingerprint_preview": fingerprint_hash[:8] if fingerprint_hash else ""}, "success"
            )

        redirect = RedirectResponse(url="/dashboard", status_code=302)
        redirect.delete_cookie("saml_state")
        redirect.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=settings.JWT_EXPIRATION_HOURS * 3600,
        )
        redirect.set_cookie(
            key="refresh_token",
            value=refresh_token_plaintext,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 3600,
        )
        return redirect
    except SAMLError as e:
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.LOGIN,
            None, None, client_ip, user_agent,
            {"method": "saml", "error": str(e)}, "failure"
        )
        # 告警检测：登录失败
        background_tasks.add_task(
            _alert_service.check_and_alert,
            AuditEventType.LOGIN, None, client_ip, None, None,
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status.in_(["starting", "running"]),
        )
        .all()
    )
    for sess in active_sessions:
        try:
            await gotty_service.stop_gotty(sess.gotty_pid, sess.gotty_port)
            sess.status = "closed"
        except Exception:
            pass
    db.commit()

    # 撤销 Refresh Token
    if refresh_token:
        token_service.revoke_all_user_tokens(db, current_user.id)

    # 将 Access Token 加入黑名单
    if access_token:
        payload = decode_access_token(access_token)
        if payload and payload.get("jti"):
            from datetime import datetime
            exp = payload.get("exp")
            expires_at = datetime.utcfromtimestamp(exp) if exp else datetime.utcnow()
            token_service.blacklist_access_token(db, payload["jti"], current_user.id, expires_at)

    # 审计日志：登出
    background_tasks.add_task(
        _audit_service.log, db, AuditEventType.LOGOUT,
        current_user.id, current_user.username,
        _get_client_ip(request), request.headers.get("User-Agent", ""),
        {}, "success"
    )

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")

async def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.group import UserGroup
    from app.models.permission import UserPermission
    from app.models.preference import UserPreference

    groups = [g.group_name for g in db.query(UserGroup).filter_by(user_id=current_user.id).all()]
    perm = db.query(UserPermission).filter_by(user_id=current_user.id).first()
    pref = db.query(UserPreference).filter_by(user_id=current_user.id).first()

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

    preferences = {}
    if pref:
        preferences = {
            "language": pref.language,
            "theme": pref.theme,
            "timezone": pref.timezone,
        }

    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "groups": groups,
            "permissions": permissions,
            "preferences": preferences,
        },
    }


@router.post("/device/register")
async def register_device(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登录后由前端主动上报设备指纹（用于 SAML 跨站 POST 无法携带 cookie 的场景）"""
    body = await request.json()
    fingerprint_hash = body.get("fingerprint", "")
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    if not fingerprint_hash:
        return {"success": True, "data": {"registered": False}}

    is_new_device = device_service.process_login(db, current_user.id, fingerprint_hash, client_ip, user_agent)

    if is_new_device:
        background_tasks.add_task(
            _audit_service.log, db, AuditEventType.NEW_DEVICE_LOGIN,
            current_user.id, current_user.username, client_ip, user_agent,
            {"fingerprint_preview": fingerprint_hash[:8]}, "success"
        )

    return {"success": True, "data": {"registered": True, "is_new_device": is_new_device}}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """使用 Refresh Token 轮换签发新的 Access Token 和 Refresh Token"""
    if not refresh_token:
        raise HTTPException(status_code=401, detail={"code": "NO_REFRESH_TOKEN", "message": "Refresh token missing"})

    new_refresh = token_service.rotate_refresh_token(db, refresh_token)
    if not new_refresh:
        raise HTTPException(status_code=401, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"})

    user_id = token_service.verify_refresh_token(db, new_refresh)
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"})

    expires_in = settings.JWT_EXPIRATION_HOURS * 3600
    new_access = create_access_token(
        {"sub": str(user_id)},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    )

    response.set_cookie(key="access_token", value=new_access, httponly=True, samesite="lax", max_age=expires_in)
    response.set_cookie(key="refresh_token", value=new_refresh, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return {"success": True, "data": {"expires_in": expires_in}}
