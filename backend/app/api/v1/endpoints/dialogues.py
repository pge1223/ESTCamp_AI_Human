import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db, AsyncSessionLocal
from app.models.session import Session, SessionStatus
from app.models.character import Character
from app.models.dialogue import Dialogue, SpeakerType
from app.models.api_log import ApiLog
from app.schemas.dialogue import DialogueStreamRequest, DialogueResponse
from app.services import llm
from app.services.llm_router import calc_cost

router = APIRouter()
logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 10


def _to_contents(history: list[dict], user_message: str) -> list[dict]:
    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in history
    ]
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


async def _get_active_session(session_id: uuid.UUID, db: AsyncSession) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="활성화된 세션이 아닙니다.")
    return session


@router.get("/", response_model=list[DialogueResponse])
async def list_dialogues(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dialogue)
        .where(Dialogue.session_id == session_id)
        .order_by(Dialogue.turn_order)
    )
    return result.scalars().all()


@router.post("/stream")
async def stream_dialogue(
    session_id: uuid.UUID,
    body: DialogueStreamRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """사용자 발화 저장 → 대화 히스토리 조회 → AI 전체 응답 → 저장 → 단일 SSE 이벤트"""
    session_obj = await _get_active_session(session_id, db)

    char_result = await db.execute(select(Character).where(Character.id == body.character_id))
    character = char_result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")

    count_result = await db.execute(
        select(func.count()).select_from(Dialogue).where(Dialogue.session_id == session_id)
    )
    turn_count = count_result.scalar()

    # 10턴 초과 시 오래된 대화 요약 (컨텍스트 압축)
    if turn_count > CONTEXT_WINDOW:
        old_result = await db.execute(
            select(Dialogue)
            .where(Dialogue.session_id == session_id)
            .order_by(Dialogue.turn_order)
            .limit(turn_count - CONTEXT_WINDOW)
        )
        old_dialogues = old_result.scalars().all()
        block = "\n".join(
            f"{'사용자' if d.speaker_type == SpeakerType.USER else 'AI'}: {d.content}"
            for d in old_dialogues
        )
        sum_system = (
            "당신은 소설 대화 요약 전문가입니다. "
            "아래 대화의 핵심 사건, 인물 관계, 감정 흐름을 3~4문장으로 요약하세요. "
            "이후 이야기 전개에 필요한 맥락이 유지되도록 간결하게 작성하세요."
        )
        sum_contents = [{"role": "user", "parts": [{"text": f"다음 대화를 요약해주세요:\n\n{block}"}]}]
        new_summary = await llm.generate(sum_system, sum_contents)
        session_obj.context_summary = new_summary
        await db.commit()
        logger.info("[context] 요약 저장 완료 — session=%s turns=%d", session_id, turn_count)

    # 사용자 발화 저장
    user_dialogue = Dialogue(
        session_id=session_id,
        speaker_type=SpeakerType.USER,
        content=body.content,
        turn_order=turn_count,
    )
    db.add(user_dialogue)
    await db.flush()

    # 최근 CONTEXT_WINDOW개 히스토리 조회
    history_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.session_id == session_id)
        .order_by(Dialogue.turn_order.desc())
        .limit(CONTEXT_WINDOW)
    )
    recent = list(reversed(history_result.scalars().all()))

    history: list[dict] = []
    if session_obj.context_summary:
        history.append({"role": "user", "content": f"[이전 대화 요약]\n{session_obj.context_summary}"})
        history.append({"role": "assistant", "content": "이전 맥락을 이해했습니다. 계속 이야기 나눠요."})

    history += [
        {
            "role": "user" if d.speaker_type == SpeakerType.USER else "assistant",
            "content": d.content,
        }
        for d in recent
    ]

    # AI 전체 응답
    system_prompt = character.prompt or ""
    contents = _to_contents(history[-10:], body.content)
    usage_out: list = []

    try:
        ai_text = await llm.generate(system_prompt, contents, usage_out=usage_out)
    except Exception as e:
        logger.error("[dialogues] LLM 호출 실패 — session=%s: %s", session_id, e)
        async def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    # AI 응답 + ApiLog 저장
    ai_dialogue = Dialogue(
        session_id=session_id,
        speaker_type=SpeakerType.CHARACTER,
        character_id=body.character_id,
        content=ai_text,
        turn_order=turn_count + 1,
    )
    db.add(ai_dialogue)

    if usage_out:
        u = usage_out[0]
        api_log = ApiLog(
            session_id=session_id,
            endpoint=f"POST /sessions/{session_id}/dialogues/stream",
            model_used=u["model"],
            prompt_tokens=u["prompt_tokens"],
            completion_tokens=u["completion_tokens"],
            total_cost=calc_cost(u["model"], u["prompt_tokens"], u["completion_tokens"]),
        )
        db.add(api_log)
        logger.info(
            "[api_log] 저장 — model=%s prompt=%d completion=%d cost=%.8f",
            u["model"], u["prompt_tokens"], u["completion_tokens"],
            calc_cost(u["model"], u["prompt_tokens"], u["completion_tokens"]),
        )

    await db.commit()
    logger.info("[dialogues] AI 응답 저장 완료 — session=%s turn=%d", session_id, turn_count + 1)

    # 단일 SSE 이벤트로 전달 (프론트에서 타이핑 효과 처리)
    async def generate():
        payload = json.dumps(
            {"character": character.name, "text": ai_text, "done": True},
            ensure_ascii=False,
        )
        yield f"data: {payload}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
