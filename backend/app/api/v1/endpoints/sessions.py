import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.api_log import ApiLog
from app.models.novel import Novel
from app.models.session import Session, SessionStatus
from app.schemas.session import SessionCreate, SessionResponse, SessionListItem

router = APIRouter()
logger = logging.getLogger(__name__)

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("/", response_model=list[SessionListItem])
async def list_sessions(
    user_id: uuid.UUID = DUMMY_USER_ID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.world))
        .where(Session.user_id == user_id)
        .order_by(Session.started_at.desc())
    )
    sessions = result.scalars().all()

    session_ids = [s.id for s in sessions]
    novel_result = await db.execute(
        select(Novel.session_id).where(
            Novel.session_id.in_(session_ids),
            Novel.content != "",
        )
    )
    has_novel_set = {row[0] for row in novel_result.fetchall()}

    return [
        SessionListItem(
            id=s.id,
            world_id=s.world_id,
            world_title=s.world.title,
            world_genre=s.world.genre,
            author_id=s.author_id,
            status=s.status,
            started_at=s.started_at,
            ended_at=s.ended_at,
            has_novel=s.id in has_novel_set,
        )
        for s in sessions
    ]


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = Session(**body.model_dump())
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info("세션 시작: %s (user=%s, world=%s)", session.id, body.user_id, body.world_id)
    return session


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    # ApiLog: nullable FK, DB CASCADE 없음 → 먼저 삭제
    await db.execute(delete(ApiLog).where(ApiLog.session_id == session_id))
    # Session 삭제 (Dialogue/Novel은 DB FK CASCADE로 처리)
    await db.execute(delete(Session).where(Session.id == session_id))
    logger.info("세션 삭제: %s", session_id)


@router.post("/{session_id}/restart", response_model=SessionResponse, status_code=201)
async def restart_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """현재 세션을 완료 처리하고, 같은 세계관·주인공으로 새 세션을 생성해 반환."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    old = result.scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if old.status != SessionStatus.COMPLETED:
        old.status = SessionStatus.COMPLETED
        old.ended_at = datetime.utcnow()
        logger.info("세션 완료(restart): %s", session_id)

    new_session = Session(
        world_id=old.world_id,
        user_id=old.user_id,
        protagonist_id=old.protagonist_id,
        author_id=old.author_id,
    )
    db.add(new_session)
    await db.flush()
    await db.refresh(new_session)
    logger.info("새 세션 생성(restart): %s → %s", session_id, new_session.id)
    return new_session


@router.patch("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session.status == SessionStatus.COMPLETED:
        return session

    session.status = SessionStatus.COMPLETED
    session.ended_at = datetime.utcnow()
    await db.flush()
    await db.refresh(session)
    logger.info("세션 완료: %s", session_id)
    return session
