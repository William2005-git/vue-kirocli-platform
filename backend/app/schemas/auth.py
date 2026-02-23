from typing import Optional

from pydantic import BaseModel

from app.schemas.user import UserResponse


class LoginResponse(BaseModel):
    user: UserResponse
    redirect_url: str = "/dashboard"


class MeResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    groups: list = []
    permissions: dict = {}
    preferences: dict = {}
