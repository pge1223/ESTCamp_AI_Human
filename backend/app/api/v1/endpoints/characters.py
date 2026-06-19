import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.world import World
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[CharacterResponse])
async def list_characters(world_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.world_id == world_id))
    return result.scalars().all()


@router.post("/", response_model=CharacterResponse, status_code=201)
async def create_character(
    world_id: uuid.UUID,
    body: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    world_result = await db.execute(select(World).where(World.id == world_id))
    if not world_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    character = Character(world_id=world_id, **body.model_dump())
    db.add(character)
    await db.flush()
    await db.refresh(character)
    logger.info("캐릭터 생성: %s (world=%s)", body.name, world_id)
    return character


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(world_id: uuid.UUID, character_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.world_id == world_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.world_id == world_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(character, field, value)
    await db.flush()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=204)
async def delete_character(world_id: uuid.UUID, character_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.world_id == world_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    await db.delete(character)
