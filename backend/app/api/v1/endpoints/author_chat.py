"""작가 AI 채팅 엔드포인트 — 오른쪽 패널 메타 대화"""
import json
import uuid
import logging
import re as _re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from fastapi import HTTPException
from app.database import get_db
from app.models.session import Session
from app.models.world import World
from app.models.character import Character
from app.models.dialogue import Dialogue, SpeakerType
from app.models.user_taste_profile import UserTasteProfile
from app.core.taste_recommend_prompt import (
    TASTE_RECOMMEND_SYSTEM, build_taste_section, build_novel_section,
    build_dialogue_section, build_author_taste_section, build_user_voice_section,
)
from app.services.chat_context import (
    redis_client,
    get_author_history, append_author_history, get_prev_user_questions,
    key_memos, key_history, key_summary,
)
from app.services import llm, memory, personalize
from app.prompts.author import build_author_messages
from app.core.personas import build_feedback_prompt, build_rewrite_prompt
from app.prompts.lyric import LYRIC_EXTRACT_SYSTEM, build_lyric_scene_system

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_story_context(chat_id: str, db: AsyncSession) -> tuple[str, str]:
    """세계관 문자열 + 현재 줄거리 요약 반환."""
    try:
        sid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return "", ""

    session = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
    if not session:
        return "", ""

    world = (await db.execute(select(World).where(World.id == session.world_id))).scalar_one_or_none()
    chars = (await db.execute(select(Character).where(Character.world_id == session.world_id))).scalars().all()

    parts = []
    if world:
        for label, val in (("제목", world.title), ("장르", world.genre),
                           ("배경", world.setting), ("요약", world.description), ("규칙", world.rules)):
            if val:
                parts.append(f"{label}: {val}")
    if chars:
        lines = "\n".join(
            f"- {c.name} ({getattr(c.role, 'value', c.role)}): {c.personality}" for c in chars
        )
        parts.append(f"[등장인물]\n{lines}")

    world_context  = "\n".join(parts)
    story_summary  = session.story_summary or ""
    return world_context, story_summary


async def _get_memos(chat_id: str) -> list:
    raw = await redis_client.get(key_memos(chat_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


async def _get_recent_story_turns(chat_id: str, db: AsyncSession, limit: int = 5) -> list[dict]:
    """최근 스토리 대화 N턴을 시간 오름차순으로 반환."""
    try:
        sid = uuid.UUID(chat_id)
        rows = (await db.execute(
            select(Dialogue)
            .where(Dialogue.session_id == sid)
            .order_by(Dialogue.created_at.desc())
            .limit(limit)
        )).scalars().all()
        return [
            {
                "role": "user" if r.speaker_type == SpeakerType.USER else "character",
                "content": r.content,
            }
            for r in reversed(rows)
        ]
    except Exception as e:
        logger.warning("최근 스토리 대화 조회 실패: %s", e)
        return []


# ── 스키마 ────────────────────────────────────────────────────
class AuthorMessageRequest(BaseModel):
    content: str
    author_id: str = "baekya"
    mode: str = "chat"  # 'chat' | 'feedback'
    opening_narration: str = ""


class AuthorRewriteRequest(BaseModel):
    original: str
    feedback: str
    author_id: str = "baekya"
    opening_narration: str = ""


def _parse_suggest_marker(raw: str) -> tuple[str, bool]:
    """응답에서 [SUGGEST:YES/NO] 마커를 파싱하고 제거된 텍스트와 플래그를 반환."""
    import re
    suggest = True
    # 텍스트 어디에 붙어있든 제거 (인라인 포함)
    no_match = re.search(r'\[SUGGEST:NO\]', raw)
    if no_match:
        suggest = False
    cleaned = re.sub(r'\s*\[SUGGEST:(?:YES|NO)\]', '', raw).strip()
    return cleaned, suggest


class AuthorMessageResponse(BaseModel):
    messageId: str
    content: str
    shouldRecommend: bool = True


# ── 엔드포인트 ────────────────────────────────────────────────
@router.post("/{chat_id}/author/message")
async def send_author_message(
    chat_id: str,
    body: AuthorMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthorMessageResponse:
    """
    작가 AI에게 메시지를 보내고 응답을 받는다.
    - 세계관·줄거리·메모를 컨텍스트로 주입
    - RAG로 관련 사건 회상
    - 일반 텍스트 응답 (JSON 아님)
    """
    world_context, story_summary = await _get_story_context(chat_id, db)
    if body.opening_narration:
        world_context += f"\n\n[오프닝 장면]\n{body.opening_narration}"

    logger.info("작가채팅 요청 - chat_id=%s author=%s mode=%s", chat_id, body.author_id, body.mode)

    if body.mode == "feedback":
        system_prompt = build_feedback_prompt(
            persona_id=body.author_id,
            world_context=world_context,
            story_summary=story_summary,
        )
        contents = [{"role": "user", "parts": [{"text": body.content}]}]
    else:
        memos          = await _get_memos(chat_id)
        author_history = await get_author_history(chat_id, body.author_id)

        prev_questions: list[str] = []
        if not author_history:
            prev_questions = await get_prev_user_questions(chat_id, exclude_author=body.author_id)

        relevant: list[str] = []
        try:
            relevant = await memory.retrieve_relevant(chat_id, db, body.content)
        except Exception as e:
            logger.warning("작가채팅 RAG 실패: %s", e)

        recent_story = await _get_recent_story_turns(chat_id, db, limit=5)

        context_summary = story_summary
        if relevant:
            context_summary += "\n\n[관련 사건 (RAG)]\n" + "\n".join(f"- {r}" for r in relevant)

        messages = build_author_messages(
            author_id=body.author_id,
            world_context=world_context,
            story_summary=context_summary,
            memos=memos,
            author_history=author_history,
            prev_questions=prev_questions,
            recent_story=recent_story,
            user_input=body.content,
        )
        system_prompt = messages[0]["content"]
        contents = [
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [{"text": m["content"]}]}
            for m in messages[1:]
        ]

    raw = await llm.generate(system_prompt, contents, json_mode=False)
    reply_raw = (raw or "").strip()
    reply, should_recommend = _parse_suggest_marker(reply_raw)


    await append_author_history(chat_id, body.author_id, "user", body.content)
    await append_author_history(chat_id, body.author_id, "ai", reply)

    logger.info("작가채팅 응답 - chat_id=%s suggest=%s: %s", chat_id, should_recommend, reply[:80])

    return AuthorMessageResponse(
        messageId=f"amsg_{uuid.uuid4().hex[:8]}",
        content=reply,
        shouldRecommend=should_recommend,
    )


@router.post("/{chat_id}/author/rewrite")
async def generate_rewrite(
    chat_id: str,
    body: AuthorRewriteRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthorMessageResponse:
    """
    피드백을 반영한 추천 문장 생성.
    - original: 사용자 원문
    - feedback: 방금 받은 피드백 텍스트
    """
    world_context, story_summary = await _get_story_context(chat_id, db)
    if body.opening_narration:
        world_context += f"\n\n[오프닝 장면]\n{body.opening_narration}"
    memos = await _get_memos(chat_id)
    author_history = await get_author_history(chat_id, body.author_id)

    relevant: list[str] = []
    try:
        relevant = await memory.retrieve_relevant(chat_id, db, body.original)
    except Exception as e:
        logger.warning("추천문장 RAG 실패: %s", e)

    system_prompt = build_rewrite_prompt(
        persona_id=body.author_id,
        original=body.original,
        feedback=body.feedback,
        world_context=world_context,
        story_summary=story_summary,
        memos=memos,
        relevant=relevant,
        author_history=author_history,
    )
    contents = [{"role": "user", "parts": [{"text": "위 원문과 피드백을 바탕으로 추천 문장을 작성해줘."}]}]

    raw = await llm.generate(system_prompt, contents, json_mode=False)
    reply = (raw or "").strip()

    logger.info("추천문장 생성 - chat_id=%s author=%s: %s", chat_id, body.author_id, reply[:60])

    return AuthorMessageResponse(
        messageId=f"amsg_{uuid.uuid4().hex[:8]}",
        content=reply,
    )


class TasteRecommendRequest(BaseModel):
    user_id: str
    author_id: str = "baekya"


class RecommendationItem(BaseModel):
    type: str
    narration: str
    dialogue: str
    reason: str


class TasteRecommendResponse(BaseModel):
    recommendations: list[RecommendationItem]


@router.post("/{chat_id}/author/taste-recommend")
async def taste_recommend(
    chat_id: str,
    body: TasteRecommendRequest,
    db: AsyncSession = Depends(get_db),
) -> TasteRecommendResponse:
    """취향저격 AI - 사용자 취향 + 소설 상황 + 이전 대화 기반 다음 문장 추천."""
    # 1. 취향 프로필 조회
    taste_profile: dict = {}
    try:
        uid = uuid.UUID(body.user_id)
        row = (await db.execute(
            select(UserTasteProfile).where(UserTasteProfile.user_id == uid)
        )).scalar_one_or_none()
        if row and row.taste_profile:
            taste_profile = row.taste_profile
    except Exception as e:
        logger.warning("취향 프로필 조회 실패: %s", e)

    # 2. 소설 컨텍스트 (세계관 + 줄거리 요약)
    world_context, story_summary = await _get_story_context(chat_id, db)

    # Redis summary가 DB보다 최신일 수 있으므로 우선 사용
    redis_summary = await redis_client.get(key_summary(chat_id))
    if redis_summary:
        story_summary = redis_summary

    # 3. 최근 대화 — Redis에서 직접 (DB sync 주기와 무관하게 항상 최신)
    recent_dialogues: list[dict] = []
    try:
        raw_history = await redis_client.lrange(key_history(chat_id), 0, 9)
        recent_dialogues = [
            {
                "role": entry["role"] if entry["role"] == "user" else "character",
                "content": entry["content"],
            }
            for entry in (json.loads(r) for r in reversed(raw_history))
        ]
    except Exception as e:
        logger.warning("Redis 대화 기록 조회 실패: %s", e)

    # 3.5 개인화 RAG: 사용자가 저장한 문장에서 '현재 장면과 가까운 본인 톤' 검색
    #     (정적 취향 프로필을 넘어, 실제 저장 문장으로 취향을 근거화 — 없으면 빈 섹션)
    scene_query = (recent_dialogues[-1]["content"] if recent_dialogues else "") or story_summary
    user_voice: list[str] = []
    try:
        user_voice = await personalize.retrieve_user_voice(db, body.user_id, scene_query, k=3)
    except Exception as e:
        logger.warning("개인화 RAG 실패(생략): %s", e)

    # 4. 프롬프트 조립
    system_prompt = TASTE_RECOMMEND_SYSTEM.format(
        taste_section=build_taste_section(taste_profile),
        user_voice_section=build_user_voice_section(user_voice),
        novel_section=build_novel_section(world_context, story_summary),
        dialogue_section=build_dialogue_section(recent_dialogues),
        author_section=build_author_taste_section(body.author_id),
    )
    if user_voice:
        logger.info("개인화 RAG - chat_id=%s 저장문장 %d개 톤 참고", chat_id, len(user_voice))
    contents = [{"role": "user", "parts": [{"text": "취향에 맞는 다음 문장을 추천해주세요."}]}]

    # 5. LLM 호출 + JSON 파싱
    try:
        raw = await llm.generate(system_prompt, contents, json_mode=True)
        if not raw:
            raise ValueError("LLM 빈 응답")
        text = raw if isinstance(raw, str) else json.dumps(raw)
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)
        items = parsed.get("recommendations", [])
        result = TasteRecommendResponse(
            recommendations=[
                RecommendationItem(
                    type=str(item.get("type", "")),
                    narration=str(item.get("narration", "")),
                    dialogue=str(item.get("dialogue", "")),
                    reason=str(item.get("reason", "")),
                )
                for item in items
            ]
        )
    except Exception as e:
        logger.error("취향저격 LLM 실패: %s", e)
        raise HTTPException(status_code=500, detail="AI 추천 생성에 실패했습니다.")

    logger.info("취향저격 추천 - chat_id=%s 추천수=%d", chat_id, len(result.recommendations))
    return result


class LyricApplyRequest(BaseModel):
    query: str                  # 노래 제목 or 가사 분위기 힌트
    mode: str = "transform"     # "transform" | "recommend"


class LyricApplyResponse(BaseModel):
    extracted: dict
    scene: str


@router.post("/{chat_id}/author/lyric-apply")
async def lyric_apply(
    chat_id: str,
    body: LyricApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> LyricApplyResponse:
    """가사적용 AI — 노래 감정을 소설 장면으로 변환/추천."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")

    world_context, story_summary = await _get_story_context(chat_id, db)

    # Redis summary 우선
    redis_summary = await redis_client.get(key_summary(chat_id))
    if redis_summary:
        story_summary = redis_summary

    # 최근 스토리 대화 (변환 모드에서 "현재 장면" 파악용)
    recent_turns = await _get_recent_story_turns(chat_id, db, limit=6)

    # ── Step 1: 노래 감정 추출 (가사 원문 미사용) ──────────────
    try:
        raw_extract = await llm.generate(
            LYRIC_EXTRACT_SYSTEM,
            [{"role": "user", "content": body.query}],
            json_mode=True,
        )
        extracted: dict = json.loads(raw_extract) if isinstance(raw_extract, str) else raw_extract
    except Exception as e:
        logger.error("가사 감정 추출 실패: %s", e)
        raise HTTPException(status_code=500, detail="감정 분석에 실패했습니다.")

    # ── Step 2: 장면 생성 (추출된 메타데이터만 사용, 가사 미전달) ──
    scene_system = build_lyric_scene_system(body.mode, world_context, story_summary, recent_turns)
    emotion_summary = (
        f"감정: {extracted.get('emotion', '')}\n"
        f"주제: {extracted.get('theme', '')}\n"
        f"분위기: {extracted.get('mood', '')}\n"
        f"강도: {extracted.get('intensity', 0.7)}\n"
        f"서사: {extracted.get('narrative', '')}"
    )
    try:
        scene = await llm.generate(
            scene_system,
            [{"role": "user", "content": f"[감정 데이터]\n{emotion_summary}"}],
            json_mode=False,
        )
    except Exception as e:
        logger.error("장면 생성 실패: %s", e)
        raise HTTPException(status_code=500, detail="장면 생성에 실패했습니다.")

    logger.info("가사적용 - chat_id=%s mode=%s", chat_id, body.mode)
    return LyricApplyResponse(extracted=extracted, scene=scene.strip())


@router.get("/{chat_id}/author/history")
async def get_author_chat_history(
    chat_id: str,
    author_id: str = Query(default="baekya"),
):
    """작가 AI 채팅 히스토리 조회."""
    history = await get_author_history(chat_id, author_id)
    return {"history": list(reversed(history))}
