from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class UserTasteProfile(Base):
    __tablename__ = "user_taste_profile"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    selected_works = Column(JSONB, nullable=False, default=list)
    taste_profile = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
