from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: str
    user_id: int
    username: Optional[str] = None
    gotty_url: str
    random_token: str
    gotty_pid: Optional[int] = None
    gotty_port: Optional[int] = None
    status: str
    started_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    duration_seconds: int = 0

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int
    limit: int
    offset: int


class StartSessionResponse(BaseModel):
    session_id: str
    gotty_url: str
    random_token: str
    status: str
    started_at: Optional[datetime] = None
