import uuid
from datetime import datetime
from sqlalchemy import JSON, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    # 오탈자 개인 오답노트: { "<틀린표기>": {"corrected": str, "type": str, "count": int} }
    error_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    worlds: Mapped[list["World"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    api_logs: Mapped[list["ApiLog"]] = relationship(back_populates="user")
    saved_sentences: Mapped[list["SavedSentence"]] = relationship(back_populates="user", cascade="all, delete-orphan")
