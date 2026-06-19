import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, ForeignKey, Boolean, func
from sqlalchemy import Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any
from app.database import Base


class CharacterRole(str, Enum):
    PROTAGONIST = "protagonist"
    SUPPORTING = "supporting"
    VILLAIN = "villain"
    NARRATOR = "narrator"


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)  # 기기별 랜덤 식별자, FK 없음
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[CharacterRole] = mapped_column(SAEnum(CharacterRole), nullable=False)
    personality: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    address_rules: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True, default=None)
    is_ai_controlled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    world: Mapped["World"] = relationship(back_populates="characters")
