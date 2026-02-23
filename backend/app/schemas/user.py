from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PermissionSchema(BaseModel):
    max_concurrent_sessions: int = 3
    max_session_duration_hours: int = 2
    daily_session_quota: int = 10
    can_start_terminal: bool = True
    can_view_monitoring: bool = True
    can_export_data: bool = False

    class Config:
        from_attributes = True


class PreferenceSchema(BaseModel):
    language: str = "zh-CN"
    theme: str = "light"
    timezone: str = "Asia/Shanghai"

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "user"
    status: str = "active"


class UserResponse(UserBase):
    id: int
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    groups: List[str] = []
    permissions: Optional[PermissionSchema] = None
    preferences: Optional[PreferenceSchema] = None

    class Config:
        from_attributes = True


class UserListItem(UserBase):
    id: int
    last_login_at: Optional[datetime] = None
    total_sessions: int = 0

    class Config:
        from_attributes = True


class UpdatePermissionsRequest(BaseModel):
    max_concurrent_sessions: Optional[int] = None
    max_session_duration_hours: Optional[int] = None
    daily_session_quota: Optional[int] = None
    can_start_terminal: Optional[bool] = None
    can_view_monitoring: Optional[bool] = None
    can_export_data: Optional[bool] = None


class UpdatePreferencesRequest(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None
