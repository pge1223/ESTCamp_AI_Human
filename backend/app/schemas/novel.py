import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.novel import NovelStatus


class NovelUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class NovelResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    content: str
    status: NovelStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
