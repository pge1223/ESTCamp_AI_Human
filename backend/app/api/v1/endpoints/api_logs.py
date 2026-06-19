import uuid
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date

from app.database import get_db
from app.models.api_log import ApiLog
from app.models.user import User
from app.schemas.api_log import ApiLogResponse, ApiLogSummary

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[ApiLogResponse])
async def list_logs(
    session_id: uuid.UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """호출 로그 목록 조회 (session_id로 필터 가능)"""
    query = select(ApiLog).order_by(ApiLog.created_at.desc()).limit(limit)
    if session_id:
        query = query.where(ApiLog.session_id == session_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary", response_model=list[ApiLogSummary])
async def get_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """일별 토큰 사용량 및 비용 요약 (보고서용)"""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            cast(ApiLog.created_at, Date).label("date"),
            func.count(ApiLog.id).label("total_calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("total_completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("total_cost"),
        )
        .where(ApiLog.created_at >= since)
        .group_by(cast(ApiLog.created_at, Date))
        .order_by(cast(ApiLog.created_at, Date).desc())
    )
    rows = result.all()
    return [
        ApiLogSummary(
            date=str(row.date),
            total_calls=row.total_calls,
            total_prompt_tokens=row.total_prompt_tokens,
            total_completion_tokens=row.total_completion_tokens,
            total_cost=round(row.total_cost, 8),
        )
        for row in rows
    ]


@router.get("/by-model")
async def get_by_model(db: AsyncSession = Depends(get_db)):
    """모델별 토큰 사용량·비용 집계 (어떤 엔진이 토큰을 얼마나 썼나)."""
    result = await db.execute(
        select(
            ApiLog.model_used.label("model"),
            func.count(ApiLog.id).label("calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("cost"),
        )
        .group_by(ApiLog.model_used)
        .order_by(func.sum(ApiLog.total_cost).desc())
    )
    return [
        {
            "model": row.model or "(unknown)",
            "calls": row.calls,
            "prompt_tokens": row.prompt_tokens,
            "completion_tokens": row.completion_tokens,
            "total_tokens": row.prompt_tokens + row.completion_tokens,
            "total_cost_usd": round(row.cost, 6),
        }
        for row in result.all()
    ]


@router.get("/session/{session_id}")
async def get_session_usage(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """세션별 토큰 사용량·비용 집계 (이 소설 하나에 토큰이 얼마나 들었나)."""
    result = await db.execute(
        select(
            func.count(ApiLog.id).label("calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("cost"),
        ).where(ApiLog.session_id == session_id)
    )
    row = result.one()
    return {
        "session_id": str(session_id),
        "calls": row.calls,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens": row.prompt_tokens + row.completion_tokens,
        "total_cost_usd": round(row.cost, 6),
    }


@router.get("/total")
async def get_total(db: AsyncSession = Depends(get_db)):
    """전체 누적 토큰 사용량 및 비용"""
    result = await db.execute(
        select(
            func.count(ApiLog.id).label("total_calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("total_completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("total_cost"),
        )
    )
    row = result.one()
    return {
        "total_calls": row.total_calls,
        "total_prompt_tokens": row.total_prompt_tokens,
        "total_completion_tokens": row.total_completion_tokens,
        "total_tokens": row.total_prompt_tokens + row.total_completion_tokens,
        "total_cost_usd": round(row.total_cost, 6),
    }

@router.get("/dashboard")
async def get_dashboard(
    start_date: str,
    end_date: str,
    db: AsyncSession = Depends(get_db),
):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    daily_result = await db.execute(
        select(
            cast(ApiLog.created_at, Date).label("date"),
            func.count(ApiLog.id).label("total_calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("total_completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("total_cost"),
        )
        .where(ApiLog.created_at >= start)
        .where(ApiLog.created_at < end)
        .group_by(cast(ApiLog.created_at, Date))
        .order_by(cast(ApiLog.created_at, Date).asc())
    )

    user_result = await db.execute(
        select(
            ApiLog.user_id,
            User.username,
            User.email,
            func.count(ApiLog.id).label("total_calls"),
            func.coalesce(func.sum(ApiLog.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(ApiLog.completion_tokens), 0).label("total_completion_tokens"),
            func.coalesce(func.sum(ApiLog.total_cost), 0.0).label("total_cost"),
            func.max(ApiLog.created_at).label("last_used_at"),
        )
        .outerjoin(User, ApiLog.user_id == User.id)
        .where(ApiLog.created_at >= start)
        .where(ApiLog.created_at < end)
        .group_by(ApiLog.user_id, User.username, User.email)
        .order_by(func.sum(ApiLog.prompt_tokens + ApiLog.completion_tokens).desc())
    )

    daily_rows = daily_result.all()
    user_rows = user_result.all()

    return {
        "daily": [
            {
                "date": str(row.date),
                "total_calls": row.total_calls,
                "total_prompt_tokens": row.total_prompt_tokens,
                "total_completion_tokens": row.total_completion_tokens,
                "total_tokens": row.total_prompt_tokens + row.total_completion_tokens,
                "total_cost_usd": round(row.total_cost, 6),
            }
            for row in daily_rows
        ],
        "users": [
            {
                "user_id": str(row.user_id) if row.user_id else None,
                "username": row.username or "비회원",
                "email": row.email,
                "total_calls": row.total_calls,
                "total_prompt_tokens": row.total_prompt_tokens,
                "total_completion_tokens": row.total_completion_tokens,
                "total_tokens": row.total_prompt_tokens + row.total_completion_tokens,
                "total_cost_usd": round(row.total_cost, 6),
                "last_used_at": row.last_used_at,
            }
            for row in user_rows
        ],
    }