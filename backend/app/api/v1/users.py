from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
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
