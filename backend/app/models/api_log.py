import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ApiLog(Base):
    __tablename__ = "api_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="api_logs")
    session: Mapped["Session | None"] = relationship(back_populates="api_logs")
