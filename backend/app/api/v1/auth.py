from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import SAMLError
from app.core.saml import get_saml_settings, is_saml_configured, parse_saml_attributes
from app.core.security import create_access_token
from app.models.session import Session as SessionModel
from app.services.gotty_service import gotty_service
from app.services.user_service import create_or_update_user

router = APIRouter()


@router.get("/saml/login")
async def saml_login():
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
        login_url = auth.login()
        return RedirectResponse(url=login_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/saml/callback")
async def saml_callback(request: Request, response: Response, db: Session = Depends(get_db)):
    if not is_saml_configured():
        raise HTTPException(status_code=503, detail="SAML not configured")
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
        token = create_access_token(
            {"sub": str(user.id)},
            expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        )
        redirect = RedirectResponse(url="/dashboard", status_code=302)
        redirect.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=settings.JWT_EXPIRATION_HOURS * 3600,
        )
        return redirect
    except SAMLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
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

    response.delete_cookie("access_token")
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
