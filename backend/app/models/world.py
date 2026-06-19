import uuid
from datetime import datetime
from sqlalchemy import JSON, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(50), default="")
    setting: Mapped[str] = mapped_column(Text, default="")   # 시대/공간 배경
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_facts: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    # 맞춤법 교정 보호 용어집: 자동 추출(LLM) + 사용자 '넘기기' 누적. None=미추출, []=추출했으나 없음
    glossary: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    # 인물 간 관계도(설정집 등장인물 탭) — 사용자가 직접 입력. [{from, to, label}] (from/to=character.id 문자열)
    relations: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="worlds")
    characters: Mapped[list["Character"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="world")
