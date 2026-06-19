"""Redis 기반 채팅 컨텍스트 관리 — 스토리 채팅 / 작가 AI 채팅 공용"""
import json
import uuid
import logging

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models.dialogue import Dialogue, SpeakerType
from app.models.session import Session

logger = logging.getLogger(__name__)

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

RECENT_DIALOGUE_LIMIT = 20
PROMPT_HISTORY_LIMIT  = 10
DB_SYNC_INTERVAL      = 5


# ── Redis 키 규칙 ──────────────────────────────────────────────
def key_history(chat_id: str) -> str:
    return f"session:{chat_id}:history"

def key_state(chat_id: str) -> str:
    return f"session:{chat_id}:state"

def key_characters(chat_id: str) -> str:
    return f"session:{chat_id}:characters"

def key_summary(chat_id: str) -> str:
    return f"session:{chat_id}:summary"

def key_turn(chat_id: str) -> str:
    return f"session:{chat_id}:turn"

def key_memos(chat_id: str) -> str:
    return f"session:{chat_id}:memos"

def key_author_history(chat_id: str, author_id: str) -> str:
    return f"session:{chat_id}:author_history:{author_id}"

_KNOWN_AUTHORS = ["baekya", "charoun", "hanyeoreum", "kimdohyeon"]


# ── 스토리 컨텍스트 조회 (DB fallback 포함) ──────────────────
async def get_context(chat_id: str, db: AsyncSession) -> dict:
    history_raw = await redis_client.lrange(key_history(chat_id), 0, RECENT_DIALOGUE_LIMIT - 1)
    state      = await redis_client.get(key_state(chat_id))
    characters = await redis_client.get(key_characters(chat_id)) or ""
    summary    = await redis_client.get(key_summary(chat_id))

    if state is None or summary is None:
        try:
            session_uuid = uuid.UUID(chat_id)
            session_result = await db.execute(select(Session).where(Session.id == session_uuid))
            session = session_result.scalar_one_or_none()
            if session:
                if state is None:
                    state = session.current_state or ""
                    if state:
                        await redis_client.set(key_state(chat_id), state)
                        logger.info("Redis state 복원 - chat_id=%s", chat_id)
                if summary is None:
                    summary = session.story_summary or ""
                    if summary:
                        await redis_client.set(key_summary(chat_id), summary)
                        logger.info("Redis summary 복원 - chat_id=%s", chat_id)
        except Exception as e:
            logger.warning("DB fallback 실패 - chat_id=%s: %s", chat_id, e)

    state   = state   or ""
    summary = summary or ""

    if not history_raw:
        try:
            session_uuid = uuid.UUID(chat_id)
            rows = await db.execute(
                select(Dialogue)
                .where(Dialogue.session_id == session_uuid)
                .order_by(Dialogue.turn_order.desc())
                .limit(RECENT_DIALOGUE_LIMIT)
            )
            dialogues = list(reversed(rows.scalars().all()))
            if dialogues:
                for d in dialogues:
                    role  = "user" if d.speaker_type == SpeakerType.USER else "ai"
                    entry = json.dumps({"role": role, "content": d.content}, ensure_ascii=False)
                    await redis_client.rpush(key_history(chat_id), entry)
                await redis_client.ltrim(key_history(chat_id), 0, RECENT_DIALOGUE_LIMIT - 1)
                history_raw = await redis_client.lrange(key_history(chat_id), 0, RECENT_DIALOGUE_LIMIT - 1)
                logger.info("Redis history 복원 - chat_id=%s (%d개)", chat_id, len(dialogues))
        except Exception as e:
            logger.warning("history DB fallback 실패 - chat_id=%s: %s", chat_id, e)

    history = [json.loads(item) for item in history_raw]

    memos_raw = await redis_client.get(key_memos(chat_id))
    memos: list = []
    if memos_raw:
        try:
            memos = json.loads(memos_raw)
        except Exception:
            pass

    return {
        "history":    history,
        "state":      state,
        "characters": characters,
        "summary":    summary,
        "memos":      memos,
    }


async def init_context_if_empty(chat_id: str, state: str, characters: str, summary: str):
    if not await redis_client.exists(key_state(chat_id)) and state:
        await redis_client.set(key_state(chat_id), state)
    if not await redis_client.exists(key_characters(chat_id)) and characters:
        await redis_client.set(key_characters(chat_id), characters)
    if not await redis_client.exists(key_summary(chat_id)) and summary:
        await redis_client.set(key_summary(chat_id), summary)


# ── 스토리 히스토리 갱신 ──────────────────────────────────────
async def append_history(chat_id: str, role: str, content: str) -> int:
    entry = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    await redis_client.lpush(key_history(chat_id), entry)
    await redis_client.ltrim(key_history(chat_id), 0, RECENT_DIALOGUE_LIMIT - 1)
    return int(await redis_client.incr(key_turn(chat_id)))


async def update_state(chat_id: str, new_state: str):
    await redis_client.set(key_state(chat_id), new_state)


async def sync_to_db(chat_id: str):
    state   = await redis_client.get(key_state(chat_id))   or ""
    summary = await redis_client.get(key_summary(chat_id)) or ""
    try:
        session_uuid = uuid.UUID(chat_id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Session).where(Session.id == session_uuid))
            session = result.scalar_one_or_none()
            if session:
                session.current_state = state
                session.story_summary = summary
                await db.commit()
                logger.info("DB 동기화 완료 - chat_id=%s", chat_id)
    except Exception as e:
        logger.error("DB 동기화 실패 - chat_id=%s: %s", chat_id, e)


# ── 작가 AI 히스토리 (작가별 분리) ───────────────────────────
async def get_author_history(chat_id: str, author_id: str) -> list[dict]:
    raw = await redis_client.lrange(key_author_history(chat_id, author_id), 0, RECENT_DIALOGUE_LIMIT - 1)
    return [json.loads(item) for item in raw]


async def append_author_history(chat_id: str, author_id: str, role: str, content: str):
    entry = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    await redis_client.lpush(key_author_history(chat_id, author_id), entry)
    await redis_client.ltrim(key_author_history(chat_id, author_id), 0, RECENT_DIALOGUE_LIMIT - 1)


async def get_prev_user_questions(chat_id: str, exclude_author: str) -> list[str]:
    """다른 작가들과 나눈 대화에서 사용자 메시지만 추출 — 작가 전환 시 상황 전달용."""
    questions: list[str] = []
    for author_id in _KNOWN_AUTHORS:
        if author_id == exclude_author:
            continue
        raw = await redis_client.lrange(key_author_history(chat_id, author_id), 0, 19)
        for item in raw:
            h = json.loads(item)
            if h["role"] == "user":
                questions.append(h["content"])
    return questions[-5:]  # 가장 최근 5개만
