import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.dialogue import SpeakerType


class DialogueStreamRequest(BaseModel):
    content: str
    character_id: uuid.UUID


class DialogueResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    speaker_type: SpeakerType
    speaker: str | None
    character_id: uuid.UUID | None
    content: str
    turn_order: int
    created_at: datetime
