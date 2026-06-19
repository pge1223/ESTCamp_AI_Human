"""개인화 RAG — 사용자가 ✓ 저장한 문장에서 '본인 톤'을 의미검색.

취향저격 추천(taste_recommend)의 근거. 정적 취향 프로필(선호장르·키워드)을 넘어,
사용자가 실제로 저장한 문장 중 **현재 장면과 가까운 것**을 retrieve해 추천 few-shot으로
제공한다 → "진짜 취향저격".

개인화 경계: 추천/코치 층에만 적용한다. 소설 '출력 문체'에 사용자 정체성을 주입하는 게
아니라, 추천 후보의 톤 참고용일 뿐이다.

임베딩/코사인은 memory 모듈 헬퍼를 재사용한다(RAG 인프라 공유 — style.py와 동일 패턴).
"""
import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import memory
from app.models.saved_sentence import SavedSentence

logger = logging.getLogger(__name__)

# 임베딩 비용 상한 — 최근 저장 문장 N개만 후보로 둔다.
_POOL = 50


async def retrieve_user_voice(db: AsyncSession, user_id: str, query: str, k: int = 3) -> list[str]:
    """사용자가 저장한 문장 중 query(현재 장면)와 의미적으로 가장 가까운 top-K 반환.

    - 저장 문장이 없으면 빈 리스트(개인화 근거 없음 → 추천은 정적 프로필로 폴백).
    - 임베딩 실패는 최근 k개로 폴백(추천 흐름을 막지 않음).
    """
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return []

    try:
        rows = (await db.execute(
            select(SavedSentence)
            .where(SavedSentence.user_id == uid)
            .order_by(SavedSentence.created_at.desc())
            .limit(_POOL)
        )).scalars().all()
    except Exception as e:  # noqa: BLE001
        logger.warning("저장 문장 조회 실패(개인화 생략): %s", e)
        return []

    samples = [r.content.strip() for r in rows if r.content and r.content.strip()]
    if not samples:
        return []
    if not (query or "").strip():
        return samples[:k]  # 장면 정보 없으면 최근 저장 k개

    try:
        qv = (await memory._embed_cached([query]))[0]
        svs = await memory._embed_cached(samples)
    except Exception as e:  # noqa: BLE001 - 임베딩 실패 시 최근 k개 폴백
        logger.warning("개인화 임베딩 실패(최근 %d개 폴백): %s", k, e)
        return samples[:k]

    scored = sorted(
        ((s, memory._cosine(qv, v)) for s, v in zip(samples, svs) if v),
        key=lambda x: x[1],
        reverse=True,
    )
    return [s for s, _ in scored[:k]]
