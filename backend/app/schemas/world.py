import uuid
from datetime import datetime
from pydantic import BaseModel


class WorldCreate(BaseModel):
    title: str
    description: str = ""
    genre: str = ""
    setting: str = ""
    rules: str | None = None
    hidden_facts: list[str] | None = None


class WorldUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    genre: str | None = None
    setting: str | None = None
    rules: str | None = None
    hidden_facts: list[str] | None = None


class WorldResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str
    genre: str
    setting: str
    rules: str | None
    hidden_facts: list[str] | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
