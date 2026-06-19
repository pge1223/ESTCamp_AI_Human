"""첫 장면(오프닝) 생성 엔드포인트 — 언제든 삭제 가능한 독립 모듈"""

import uuid
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import llm
from app.models.session import Session
from app.prompts.opening import build_opening_system, build_opening_user_prompt
from app.core.personas import AUTHOR_ID_MAP

# chats.py의 _build_world_context를 재사용
from app.api.v1.endpoints.chats import _build_world_context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{chat_id}/opening")
async def generate_opening_scene(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    """세계관 기반 첫 장면 나레이션 생성. 신규 세션 진입 시 1회 호출."""
    # 작가 persona 조회
    persona_key = ""
    try:
        sid = uuid.UUID(chat_id)
        session = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
        if session and session.author_id:
            persona_key = AUTHOR_ID_MAP.get(session.author_id, "")
    except Exception:
        pass

    world_context = await _build_world_context(chat_id, db)
    if not world_context:
        return JSONResponse({"narration": ""})

    system = build_opening_system(persona_key)
    user_prompt = build_opening_user_prompt(world_context)
    contents = [{"role": "user", "parts": [{"text": user_prompt}]}]

    try:
        narration = await llm.generate(system, contents)
        narration = narration.strip().strip('"').strip()
        logger.info("[opening] 생성 완료 — chat_id=%s persona=%s len=%d", chat_id, persona_key or "default", len(narration))
    except Exception as e:
        logger.error("[opening] LLM 실패 — chat_id=%s: %s", chat_id, e)
        narration = ""

    return JSONResponse({"narration": narration})
