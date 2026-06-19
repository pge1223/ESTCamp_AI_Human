import json
import logging
import re
import uuid
import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from app.database import get_db
from app.models.user import User
from app.prompts import VOICE_PROFILE_SYSTEM
from app.schemas.user import UserCreate, UserResponse, UserSync
from app.services import llm

router = APIRouter()
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("신규 유저 등록: %s", user.email)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return user

@router.post("/me", response_model=UserResponse)
async def sync_me(body: UserSync, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.id == body.id)
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    user = User(
        id=body.id,
        username=body.nickname,
        email=body.email,
        hashed_password=pwd_context.hash(secrets.token_hex(16)),
    )

    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info("Neon Auth 유저 동기화: %s", user.email)
    return user


# ── Voice Mirroring: 말투 프로파일 (F-VM) ─────────────────
class VoiceProfileBody(BaseModel):
    user_samples: list[str] = []
    guide_answers: list[str] = []
    optional_context: str = ""


@router.post("/{user_id}/voice-profile")
async def save_voice_profile(
    user_id: uuid.UUID,
    body: VoiceProfileBody,
    db: AsyncSession = Depends(get_db),
):
    """사용자 문장 샘플 → 말투 분석 → User.voice_profile 저장 (온보딩/마이페이지용)."""
    if not body.user_samples and not body.guide_answers:
        raise HTTPException(status_code=422, detail="user_samples 또는 guide_answers를 1개 이상 입력하세요.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

    parts = []
    if body.user_samples:
        parts.append("[자유 입력 문장]\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(body.user_samples)))
    if body.guide_answers:
        parts.append("[가이드 문장 답변]\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(body.guide_answers)))
    if body.optional_context:
        parts.append(f"[원하는 말투 방향]\n{body.optional_context}")
    user_msg = "\n\n".join(parts)

    try:
        raw = await llm.generate(
            VOICE_PROFILE_SYSTEM,
            [{"role": "user", "parts": [{"text": user_msg}]}],
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        profile = json.loads(cleaned)
    except Exception as e:
        logger.warning("말투 분석 실패 - user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="말투 분석 중 오류가 발생했습니다.")

    user.voice_profile = profile
    await db.flush()
    logger.info("말투 프로파일 저장 - user_id=%s", user_id)
    return {"voice_profile": profile}


@router.get("/{user_id}/voice-profile")
async def get_voice_profile(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """저장된 말투 프로파일 조회 (없으면 null)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return {"voice_profile": user.voice_profile}