import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import ForeignKey, Text, Integer, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SpeakerType(str, Enum):
    USER = "user"
    CHARACTER = "character"


class Dialogue(Base):
    __tablename__ = "dialogues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    speaker_type: Mapped[SpeakerType] = mapped_column(SAEnum(SpeakerType), nullable=False)
    speaker: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    session: Mapped["Session"] = relationship(back_populates="dialogues")
    character: Mapped["Character | None"] = relationship()
