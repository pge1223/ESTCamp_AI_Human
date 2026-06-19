import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, ForeignKey, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NovelStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    FINAL = "final"


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), default="제목 없음")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[NovelStatus] = mapped_column(SAEnum(NovelStatus), default=NovelStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    session: Mapped["Session"] = relationship(back_populates="novel")
