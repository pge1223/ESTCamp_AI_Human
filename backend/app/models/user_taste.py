from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.database import Base


class UserChatTaste(Base):
    __tablename__ = "user_chat_taste"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    chat_id = Column(UUID(as_uuid=True), nullable=False)
    works = Column(JSONB, nullable=False, default=list)
    taste_profile = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", name="uq_user_chat_taste"),
    )
