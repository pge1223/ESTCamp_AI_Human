import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.character import CharacterRole


class AddressRule(BaseModel):
    target_name: str   # 상대방 캐릭터 이름
    address: str       # 실제로 불러야 할 호칭


class CharacterCreate(BaseModel):
    user_id: str
    name: str
    role: CharacterRole
    personality: str = ""
    prompt: str = ""
    address_rules: list[AddressRule] | None = None
    is_ai_controlled: bool = True


class CharacterUpdate(BaseModel):
    name: str | None = None
    role: CharacterRole | None = None
    personality: str | None = None
    prompt: str | None = None
    address_rules: list[AddressRule] | None = None
    is_ai_controlled: bool | None = None


class CharacterResponse(BaseModel):
    id: uuid.UUID
    world_id: uuid.UUID
    user_id: str
    name: str
    role: CharacterRole
    personality: str
    prompt: str
    address_rules: list[AddressRule] | None = None
    is_ai_controlled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
