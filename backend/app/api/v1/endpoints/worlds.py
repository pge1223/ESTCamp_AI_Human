import json
import logging
import re
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.world import World
from app.models.character import Character
from app.schemas.world import WorldCreate, WorldUpdate, WorldResponse
from app.services.world_tag_classifier import classify_world_tags
from app.services import llm

router = APIRouter()
logger = logging.getLogger(__name__)

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("/", response_model=list[WorldResponse])
async def list_worlds(
    user_id: uuid.UUID = DUMMY_USER_ID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(World).where(World.user_id == user_id))
    return result.scalars().all()


@router.post("/", response_model=WorldResponse, status_code=201)
async def create_world(
    body: WorldCreate,
    user_id: uuid.UUID = DUMMY_USER_ID,
    db: AsyncSession = Depends(get_db),
):
    world = World(user_id=user_id, **body.model_dump())
    db.add(world)
    await db.flush()
    await db.refresh(world)
    logger.info("세계관 생성: %s (user=%s)", world.id, user_id)
    return world


@router.get("/{world_id}", response_model=WorldResponse)
async def get_world(world_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World).where(World.id == world_id))
    world = result.scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    return world


@router.put("/{world_id}", response_model=WorldResponse)
async def update_world(world_id: uuid.UUID, body: WorldUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World).where(World.id == world_id))
    world = result.scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(world, field, value)
    await db.flush()
    await db.refresh(world)
    return world


@router.delete("/{world_id}", status_code=204)
async def delete_world(world_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World).where(World.id == world_id))
    world = result.scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    await db.delete(world)


@router.post("/{world_id}/tags/classify", response_model=WorldResponse)
async def classify_tags(world_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World).where(World.id == world_id))
    world = result.scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")

    world_text = " ".join(filter(None, [
        world.title, world.description, world.setting, world.rules,
    ]))
    tag_result = await classify_world_tags(world_text)
    world.tags = tag_result.tags
    await db.flush()
    await db.refresh(world)
    logger.info("태그 자동분류 완료: world=%s, tags=%d개", world_id, len(tag_result.tags))
    return world


class TagsUpdate(BaseModel):
    tags: list[str]


@router.patch("/{world_id}/tags", response_model=WorldResponse)
async def update_tags(world_id: uuid.UUID, body: TagsUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World).where(World.id == world_id))
    world = result.scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")

    world.tags = body.tags
    await db.flush()
    await db.refresh(world)
    return world


_HIDDEN_FACTS_SYSTEM = (
    "당신은 추리소설 설계자입니다. 세계관과 등장인물을 분석해 "
    "독자(사용자)는 모르지만 AI 서술자가 알아야 할 핵심 숨겨진 사실을 생성합니다. "
    "JSON 배열로만 응답하세요. 설명이나 마크다운 코드블록 없이 배열만 출력합니다."
)

_HIDDEN_FACTS_PROMPT = """\
[세계관]
제목: {title}
장르: {genre}
배경: {setting}
설명: {description}
규칙: {rules}

[등장인물]
{characters}

위 세계관을 바탕으로 추리 소설의 핵심 숨겨진 사실 3~5개를 생성하세요.
- 실제 사건의 진범 또는 핵심 행위자
- 결정적 물증이나 단서의 소재
- 등장인물의 숨겨진 동기 또는 거짓 알리바이
- 독자가 나중에 '아!' 하고 반전을 느낄 복선이 될 사실

JSON 배열로만 응답: ["사실1", "사실2", ...]
"""


@router.post("/{world_id}/hidden-facts/generate", response_model=WorldResponse)
async def generate_hidden_facts(world_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    world = (await db.execute(select(World).where(World.id == world_id))).scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")

    chars = (await db.execute(select(Character).where(Character.world_id == world_id))).scalars().all()
    char_lines = "\n".join(
        f"- {c.name} ({getattr(c.role, 'value', c.role)}): {c.personality}"
        for c in chars
    ) or "등장인물 없음"

    prompt = _HIDDEN_FACTS_PROMPT.format(
        title=world.title or "",
        genre=world.genre or "",
        setting=world.setting or "",
        description=world.description or "",
        rules=world.rules or "",
        characters=char_lines,
    )

    try:
        raw = await llm.generate(
            system_prompt=_HIDDEN_FACTS_SYSTEM,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)
        facts: list[str] = json.loads(raw.strip())
        if not isinstance(facts, list):
            raise ValueError("배열이 아님")
        facts = [f for f in facts if isinstance(f, str) and f.strip()]
    except Exception as e:
        logger.error("[HiddenFacts] LLM 생성 실패: %s", e)
        raise HTTPException(status_code=500, detail="숨겨진 사실 생성에 실패했습니다.")

    world.hidden_facts = facts
    await db.flush()
    await db.refresh(world)
    logger.info("[HiddenFacts] world=%s, %d개 생성: %s", world_id, len(facts), facts)
    return world
