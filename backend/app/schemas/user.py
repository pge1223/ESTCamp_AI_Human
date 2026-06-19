import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: str
    email: str | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class UserSync(BaseModel):
    id: str
    email: str
    nickname: str
