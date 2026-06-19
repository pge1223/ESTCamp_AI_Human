import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.session import SessionStatus


class SessionCreate(BaseModel):
    world_id: uuid.UUID
    user_id: uuid.UUID       # 임시: 인증 구현 전 직접 전달
    protagonist_id: uuid.UUID
    author_id: int | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    world_id: uuid.UUID
    user_id: uuid.UUID
    protagonist_id: uuid.UUID
    author_id: int | None
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: uuid.UUID
    world_id: uuid.UUID
    world_title: str
    world_genre: str | None
    author_id: int | None
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    has_novel: bool = False
