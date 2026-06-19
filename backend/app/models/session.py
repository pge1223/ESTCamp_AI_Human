import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    protagonist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id"), nullable=False)
    author_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(SAEnum(SessionStatus), default=SessionStatus.ACTIVE)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    world: Mapped["World"] = relationship(back_populates="sessions")
    user: Mapped["User"] = relationship(back_populates="sessions")
    protagonist: Mapped["Character"] = relationship(foreign_keys=[protagonist_id])
    novel: Mapped["Novel | None"] = relationship(back_populates="session", uselist=False)
    api_logs: Mapped[list["ApiLog"]] = relationship(back_populates="session")
    dialogues: Mapped[list["Dialogue"]] = relationship(back_populates="session", cascade="all, delete-orphan")
