import logging
import re
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.session import Session, SessionStatus
from app.models.dialogue import Dialogue, SpeakerType
from app.models.world import World
from app.models.novel import Novel, NovelStatus
from app.schemas.novel import NovelUpdate, NovelResponse
from app.core.personas import AUTHOR_ID_MAP
from app.services.llm_router import LLMRouter

router = APIRouter()
logger = logging.getLogger(__name__)

llm_router = LLMRouter()


def _strip_world_suggestion(text: str) -> tuple[str, list[str]]:
    """소설 본문에서 '[세계관 추가 제안]' 블록을 분리 → (깨끗한 본문, 제안 리스트).

    build_novel_system 프롬프트가 초안 맨 아래에 '---/[세계관 추가 제안]/• ...'를 붙이는데,
    그게 원고 본문에 섞이지 않도록 떼어낸다.
    """
    idx = text.find("[세계관 추가 제안]")
    if idx == -1:
        return text.strip(), []
    story = re.sub(r"\n*-{2,}\s*$", "", text[:idx]).rstrip()
    suggestions = []
    for ln in text[idx + len("[세계관 추가 제안]"):].splitlines():
        s = ln.strip()
        if not s or set(s) <= {"-"}:   # 빈 줄 / --- 구분선 제외
            continue
        suggestions.append(re.sub(r"^[•\-*]\s*", "", s).strip())
    return story, [s for s in suggestions if s]


@router.get("/{session_id}/novel", response_model=NovelResponse)
async def get_novel(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Novel).where(Novel.session_id == session_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail="소설 초안이 없습니다.")
    return novel


@router.post("/{session_id}/novel/generate", response_model=NovelResponse, status_code=201)
async def generate_novel(
    session_id: uuid.UUID,
    use_style: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """세션의 대화 로그를 선택한 작가의 문체로 소설 초안으로 변환한다."""
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="완료된 세션만 소설로 변환할 수 있습니다.")

    existing = await db.execute(select(Novel).where(Novel.session_id == session_id))
    existing_novel = existing.scalar_one_or_none()
    if existing_novel and (existing_novel.content or "").strip():
        return existing_novel
    # 빈 본문 소설이 남아있던 경우(과거 변환 실패) → 아래에서 재생성하여 덮어쓴다.

    dialogues_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.session_id == session_id)
        .order_by(Dialogue.turn_order)
    )
    dialogues = dialogues_result.scalars().all()
    if not dialogues:
        raise HTTPException(status_code=400, detail="대화 내용이 없어 소설로 변환할 수 없습니다.")

    world_result = await db.execute(select(World).where(World.id == session.world_id))
    world = world_result.scalar_one_or_none()
    world_desc = ""
    if world:
        world_desc = "\n".join(p for p in (world.setting, world.description) if p)

    persona_id = AUTHOR_ID_MAP.get(session.author_id, "")

    # 대화 로그 → LLMRouter 입력 형식 (문체 RAG few-shot은 generate_novel 내부에서 주입)
    dialogue_history = [
        {"role": "user" if d.speaker_type == SpeakerType.USER else "assistant", "content": d.content}
        for d in dialogues
    ]

    try:
        content = await llm_router.generate_novel(
            dialogue_history, world_desc, persona_id=persona_id, use_style=use_style
        )
    except Exception as e:
        logger.error("소설 LLM 변환 실패, 폴백 사용 (session=%s): %s", session_id, e)
        content = ""

    if not content:
        content = "\n\n".join(d.content for d in dialogues)

    content, _ = _strip_world_suggestion(content)   # [세계관 추가 제안] 블록 분리 → 원고 깨끗하게

    if not content.strip():
        # 제안 블록 제거 후 비었거나 LLM 실패 → 대화 로그 원문으로 폴백(빈 원고 저장 방지)
        content = "\n\n".join(d.content for d in dialogues if d.content)
    if not content.strip():
        raise HTTPException(status_code=400, detail="대화 내용이 없어 소설로 변환할 수 없습니다.")

    if existing_novel:
        # 과거 변환 실패로 남은 빈 소설을 같은 행에 덮어쓴다(중복 생성 방지).
        existing_novel.content = content
        existing_novel.status = NovelStatus.DRAFT
        if world and world.title:
            existing_novel.title = world.title
        await db.flush()
        await db.refresh(existing_novel)
        logger.info("빈 소설 재생성: %s (session=%s, %d자)", existing_novel.id, session_id, len(content))
        return existing_novel

    novel = Novel(
        session_id=session_id,
        title=(world.title if world and world.title else "제목 없음"),
        content=content,
        status=NovelStatus.DRAFT,
    )
    db.add(novel)
    await db.flush()
    await db.refresh(novel)
    logger.info("소설 초안 생성: %s (session=%s, %d자)", novel.id, session_id, len(content))
    return novel


@router.put("/{session_id}/novel/draft", response_model=NovelResponse)
async def save_draft(session_id: uuid.UUID, body: NovelUpdate, db: AsyncSession = Depends(get_db)):
    """원고 초안 upsert — 없으면 생성, 있으면 업데이트."""
    result = await db.execute(select(Novel).where(Novel.session_id == session_id))
    novel = result.scalar_one_or_none()
    if novel:
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(novel, field, value)
    else:
        session_result = await db.execute(select(Session).where(Session.id == session_id))
        session = session_result.scalar_one_or_none()
        world_title = "제목 없음"
        if session:
            world_result = await db.execute(select(World).where(World.id == session.world_id))
            w = world_result.scalar_one_or_none()
            if w and w.title:
                world_title = w.title
        novel = Novel(
            session_id=session_id,
            title=body.title or world_title,
            content=body.content or "",
            status=NovelStatus.DRAFT,
        )
        db.add(novel)
    await db.flush()
    await db.refresh(novel)
    return novel


@router.post("/{session_id}/novel/convert", response_model=NovelResponse, status_code=201)
async def convert_dialogues_to_novel(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """진행 중인 세션의 대화를 소설 형식으로 변환 (LLM 없이 직접 조합 — 결정적·빠름).

    AI 응답(CHARACTER)은 이미 DB에 '나레이션\\n\\n"대사"' 형태로 저장되어 있으므로
    그대로 이어붙이기만 한다. 사용자 입력(USER)은 누락 없이 원문 포함.
    """
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    dialogues_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.session_id == session_id)
        .order_by(Dialogue.turn_order)
    )
    dialogues = dialogues_result.scalars().all()

    world_result = await db.execute(select(World).where(World.id == session.world_id))
    world = world_result.scalar_one_or_none()

    parts = []
    for d in dialogues:
        text = (d.content or "").strip()
        if not text:
            continue
        if d.speaker_type == SpeakerType.USER:
            # 사용자 입력: 그대로 포함 (UI에서 말풍선으로 보이던 내용)
            parts.append(text)
        else:
            # AI 응답: 이미 '나레이션\n\n"대사"' 형태로 저장됨
            parts.append(text)

    content = "\n\n".join(parts)

    existing = await db.execute(select(Novel).where(Novel.session_id == session_id))
    novel = existing.scalar_one_or_none()
    if novel:
        novel.content = content
    else:
        novel = Novel(
            session_id=session_id,
            title=(world.title if world and world.title else "제목 없음"),
            content=content,
            status=NovelStatus.DRAFT,
        )
        db.add(novel)

    await db.flush()
    await db.refresh(novel)
    logger.info("소설 변환 완료(직접): %s (session=%s, %d자)", novel.id, session_id, len(content))
    return novel


@router.patch("/{session_id}/novel", response_model=NovelResponse)
async def update_novel(session_id: uuid.UUID, body: NovelUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Novel).where(Novel.session_id == session_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail="소설 초안이 없습니다.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(novel, field, value)

    await db.flush()
    await db.refresh(novel)
    return novel
