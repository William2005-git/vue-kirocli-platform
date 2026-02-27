from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
from app.services.device_service import device_service
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me/preferences")
async def get_preferences(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    pref = service.get_user_preferences(current_user.id)
    if pref:
        data = {"language": pref.language, "theme": pref.theme, "timezone": pref.timezone}
    else:
        data = {"language": "zh-CN", "theme": "light", "timezone": "Asia/Shanghai"}
    return {"success": True, "data": data}


@router.put("/me/preferences")
async def update_preferences(
    body: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    service.update_preferences(current_user.id, body)
    return {"success": True, "message": "Preferences updated"}


# ─── 设备管理 ─────────────────────────────────────────────────────────────────

@router.get("/me/devices")
async def get_my_devices(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前用户的设备列表，标记当前设备"""
    current_fp = request.headers.get("X-Device-Fingerprint", "")
    devices = device_service.get_devices(db, current_user.id, current_fp)
    return {"success": True, "data": {"devices": devices}}


@router.put("/me/devices/{device_id}")
async def update_my_device(
    device_id: int,
    body: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新设备名称（最大 50 字符）"""
    name = body.get("device_name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="device_name is required")
    try:
        device_service.update_device_name(db, current_user.id, device_id, name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": "设备名称已更新"}


@router.delete("/me/devices/{device_id}")
async def delete_my_device(
    device_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除设备，不允许删除当前设备"""
    current_fp = request.headers.get("X-Device-Fingerprint", "")
    try:
        device_service.delete_device(db, current_user.id, device_id, current_fp)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": "设备已删除"}
