"""세션별 삽화 — 생성한 삽화(이미지)와 장면 설명(caption)을 DB에 영속 저장.

localStorage 대신 DB라 **다른 기기·계정에서도** 보인다.
이미지는 base64 data URL을 Text로 보관(데모 규모). 운영/대량 전환 시 GCS URL 저장으로 교체.
"""
import uuid
from datetime import datetime
from sqlalchemy import Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Illustration(Base):
    __tablename__ = "illustrations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(Text)             # base64 data URL
    caption: Mapped[str] = mapped_column(Text, default="")   # 어떤 장면인지(장면 설명)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
