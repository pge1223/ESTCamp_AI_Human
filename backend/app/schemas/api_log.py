import uuid
from datetime import datetime
from pydantic import BaseModel


class ApiLogResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: uuid.UUID
    session_id: uuid.UUID | None
    endpoint: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
    created_at: datetime


class ApiLogSummary(BaseModel):
    date: str
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float
