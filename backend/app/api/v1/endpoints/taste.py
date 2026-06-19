"""사용자 취향 분석 엔드포인트 — userId + chatId 단위 저장"""
import json
import uuid
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user_taste import UserChatTaste
from app.services import llm

router = APIRouter()
logger = logging.getLogger(__name__)

TASTE_GENRES = ["fantasy", "growth", "romance", "action", "sf", "mystery", "horror", "politics", "slice_of_life"]

_ANALYZE_PROMPT = """\
다음은 사용자가 좋아하는 작품 목록입니다. 이 작품들의 장르·테마·분위기·스타일을 종합 분석하여
사용자 취향 프로파일을 만들어주세요.

작품 목록:
{works_text}

아래 항목들에 대해 0.0~1.0 사이의 수치로 취향 강도를 추정하세요.
반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):
{{
  "fantasy": 0.0,
  "growth": 0.0,
  "romance": 0.0,
  "action": 0.0,
  "sf": 0.0,
  "mystery": 0.0,
  "horror": 0.0,
  "politics": 0.0,
  "slice_of_life": 0.0
}}"""


class TasteRequest(BaseModel):
    user_id: str
    works: list[str]


class TasteResponse(BaseModel):
    works: list[str]
    taste_profile: dict


@router.get("/{chat_id}/taste")
async def get_taste(
    chat_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TasteResponse:
    try:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return TasteResponse(works=[], taste_profile={})

    row = (await db.execute(
        select(UserChatTaste).where(
            UserChatTaste.user_id == uid,
            UserChatTaste.chat_id == cid,
        )
    )).scalar_one_or_none()

    if not row:
        return TasteResponse(works=[], taste_profile={})
    return TasteResponse(works=row.works or [], taste_profile=row.taste_profile or {})


@router.post("/{chat_id}/taste/analyze")
async def analyze_taste(
    chat_id: str,
    body: TasteRequest,
    db: AsyncSession = Depends(get_db),
) -> TasteResponse:
    try:
        uid = uuid.UUID(body.user_id)
        cid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return TasteResponse(works=body.works, taste_profile={})

    taste_profile: dict = {}
    if body.works:
        works_text = "\n".join(f"- {w}" for w in body.works)
        system_prompt = _ANALYZE_PROMPT.format(works_text=works_text)
        contents = [{"role": "user", "parts": [{"text": "위 작품들을 분석해서 취향 JSON을 반환해주세요."}]}]
        try:
            raw = await llm.generate(system_prompt, contents, json_mode=True)
            if raw:
                text = raw if isinstance(raw, str) else json.dumps(raw)
                # strip markdown fences if present
                text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(text)
                taste_profile = {k: float(v) for k, v in parsed.items() if k in TASTE_GENRES}
        except Exception as e:
            logger.warning("취향 LLM 분석 실패: %s", e)

    # upsert
    row = (await db.execute(
        select(UserChatTaste).where(
            UserChatTaste.user_id == uid,
            UserChatTaste.chat_id == cid,
        )
    )).scalar_one_or_none()

    if row:
        row.works = body.works
        row.taste_profile = taste_profile
    else:
        row = UserChatTaste(user_id=uid, chat_id=cid, works=body.works, taste_profile=taste_profile)
        db.add(row)

    await db.commit()
    logger.info("취향 저장 - user=%s chat=%s works=%s profile=%s", body.user_id, chat_id, body.works, taste_profile)
    return TasteResponse(works=body.works, taste_profile=taste_profile)
