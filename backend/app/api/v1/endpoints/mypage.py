"""마이페이지(내 서재) 엔드포인트"""
import json
import uuid
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.session import Session, SessionStatus
from app.models.novel import Novel
from app.models.world import World
from app.models.character import Character
from app.models.dialogue import Dialogue, SpeakerType
from app.models.saved_sentence import SavedSentence
from app.models.user_taste_profile import UserTasteProfile
from app.core.personas import AUTHOR_ID_MAP
from app.services import llm

router = APIRouter()
logger = logging.getLogger(__name__)

_AUTHOR_NAMES = {
    "baekya":     "백야",
    "charoun":    "차로운",
    "hanyeoreum": "한여름",
    "kimdohyeon": "김도현",
}


# ── 유저 조회 헬퍼 ──────────────────────────────────────────────
async def _get_user(user_id: str, db: AsyncSession) -> User:
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 user_id")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return user


# ── 1. 프로필 + 통계 ────────────────────────────────────────────
@router.get("/profile")
async def get_profile(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session).where(Session.user_id == user.id)
    )).scalars().all()

    total_works = len(sessions)
    completed_works = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)

    # 집필 일수: started_at 날짜 distinct
    active_days = len({s.started_at.date() for s in sessions if s.started_at})

    # 총 글자 수: novel content 합산
    session_ids = [s.id for s in sessions]
    novels = []
    if session_ids:
        novels = (await db.execute(
            select(Novel).where(Novel.session_id.in_(session_ids))
        )).scalars().all()
    total_chars = sum(len(n.content or "") for n in novels)

    # 자주 함께한 작가 (author_id int → persona_id)
    author_counts = Counter(
        AUTHOR_ID_MAP.get(s.author_id) for s in sessions if s.author_id is not None
    )
    total = sum(author_counts.values()) or 1
    favorite_authors = [
        {
            "author_id": aid,
            "name": _AUTHOR_NAMES.get(aid, aid),
            "count": cnt,
            "ratio": round(cnt / total * 100),
        }
        for aid, cnt in author_counts.most_common()
        if aid
    ]

    return {
        "username": user.username,
        "email": user.email,
        "stats": {
            "total_works": total_works,
            "total_chars": total_chars,
            "completed_works": completed_works,
            "active_days": active_days,
        },
        "favorite_authors": favorite_authors,
    }


# ── 2. 내 작품 목록 ─────────────────────────────────────────────
@router.get("/works")
async def get_works(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
    )).scalars().all()

    if not sessions:
        return []

    session_ids = [s.id for s in sessions]

    novels = {
        n.session_id: n
        for n in (await db.execute(
            select(Novel).where(Novel.session_id.in_(session_ids))
        )).scalars().all()
    }

    dialogue_counts = {
        row[0]: row[1]
        for row in (await db.execute(
            select(Dialogue.session_id, func.count(Dialogue.id))
            .where(Dialogue.session_id.in_(session_ids))
            .group_by(Dialogue.session_id)
        )).all()
    }

    world_ids = list({s.world_id for s in sessions})
    worlds = {
        w.id: w
        for w in (await db.execute(
            select(World).where(World.id.in_(world_ids))
        )).scalars().all()
    }

    result = []
    for s in sessions:
        novel = novels.get(s.id)
        world = worlds.get(s.world_id)
        author_str = AUTHOR_ID_MAP.get(s.author_id) if s.author_id else None
        result.append({
            "session_id": str(s.id),
            "title": novel.title if novel else (world.title if world else "제목 없음"),
            "status": s.status.value,
            "novel_status": novel.status.value if novel else None,
            "author_id": author_str,
            "author_name": _AUTHOR_NAMES.get(author_str) if author_str else None,
            "last_modified": s.updated_at.isoformat() if s.updated_at else s.started_at.isoformat(),
            "char_count": len(novel.content or "") if novel else 0,
            "dialogue_count": dialogue_counts.get(s.id, 0),
            "world": {
                "id": str(world.id),
                "title": world.title,
                "genre": world.genre,
            } if world else None,
        })
    return result


# ── 3. 작품 상세 ────────────────────────────────────────────────
@router.get("/works/{session_id}")
async def get_work_detail(
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 session_id")

    session = (await db.execute(
        select(Session).where(Session.id == sid, Session.user_id == user.id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="작품을 찾을 수 없습니다.")

    novel = (await db.execute(
        select(Novel).where(Novel.session_id == sid)
    )).scalar_one_or_none()

    world = (await db.execute(
        select(World).where(World.id == session.world_id)
    )).scalar_one_or_none()

    dialogue_count = (await db.execute(
        select(func.count(Dialogue.id)).where(Dialogue.session_id == sid)
    )).scalar_one()

    author_str = AUTHOR_ID_MAP.get(session.author_id) if session.author_id else None
    return {
        "session_id": str(session.id),
        "title": novel.title if novel else (world.title if world else "제목 없음"),
        "status": session.status.value,
        "novel_status": novel.status.value if novel else None,
        "author_id": author_str,
        "author_name": _AUTHOR_NAMES.get(author_str) if author_str else None,
        "last_modified": session.updated_at.isoformat() if session.updated_at else session.started_at.isoformat(),
        "char_count": len(novel.content or "") if novel else 0,
        "dialogue_count": dialogue_count,
        "world": {
            "id": str(world.id),
            "title": world.title,
            "genre": world.genre,
            "setting": world.setting,
            "description": world.description,
        } if world else None,
    }


# ── 4. 설정집 (캐릭터 + 세계관 + 줄거리) ───────────────────────
@router.get("/works/{session_id}/wiki")
async def get_wiki(
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 session_id")

    session = (await db.execute(
        select(Session).where(Session.id == sid, Session.user_id == user.id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="작품을 찾을 수 없습니다.")

    world = (await db.execute(
        select(World).where(World.id == session.world_id)
    )).scalar_one_or_none()

    characters = (await db.execute(
        select(Character).where(Character.world_id == session.world_id)
    )).scalars().all()

    novel = (await db.execute(
        select(Novel).where(Novel.session_id == sid)
    )).scalar_one_or_none()

    return {
        "world": {
            "id": str(world.id),
            "title": world.title,
            "genre": world.genre,
            "setting": world.setting,
            "description": world.description,
            "rules": world.rules,
        } if world else None,
        "characters": [
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role.value if hasattr(c.role, "value") else c.role,
                "personality": c.personality,
            }
            for c in characters
        ],
        "relations": (world.relations or []) if world else [],
        "story_summary": session.story_summary or "",
        "novel_title": novel.title if novel else None,
    }


@router.put("/works/{session_id}/relations")
async def save_relations(
    session_id: str,
    payload: list[dict],
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """설정집 등장인물 관계도 — 사용자가 직접 입력한 관계를 저장.

    payload: [{from, to, label}] (from/to = character.id 문자열).
    소유권 검증 후 world.relations 에 저장. 유효한 인물 id 쌍만 통과시킨다.
    """
    user = await _get_user(user_id, db)
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 session_id")

    session = (await db.execute(
        select(Session).where(Session.id == sid, Session.user_id == user.id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="작품을 찾을 수 없습니다.")

    world = (await db.execute(
        select(World).where(World.id == session.world_id)
    )).scalar_one_or_none()
    if not world:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")

    char_ids = {
        str(c.id) for c in (await db.execute(
            select(Character).where(Character.world_id == world.id)
        )).scalars().all()
    }

    cleaned = []
    for r in (payload or []):
        f, t, label = str(r.get("from", "")), str(r.get("to", "")), str(r.get("label", "")).strip()
        if f in char_ids and t in char_ids and f != t:
            item = {"from": f, "to": t, "label": label[:40]}
            for k in ("dx", "dy"):   # 사용자가 끌어 옮긴 라벨 위치 offset 보존
                v = r.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    item[k] = round(float(v), 1)
            cleaned.append(item)

    world.relations = cleaned
    await db.commit()
    return {"relations": cleaned}


# ── 5. 최근 작업 ────────────────────────────────────────────────
@router.get("/recent")
async def get_recent(
    user_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
        .limit(50)
    )).scalars().all()

    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    novels = {
        n.session_id: n
        for n in (await db.execute(
            select(Novel).where(Novel.session_id.in_(session_ids))
        )).scalars().all()
    }
    worlds = {
        w.id: w
        for w in (await db.execute(
            select(World).where(World.id.in_([s.world_id for s in sessions]))
        )).scalars().all()
    }

    # 날짜별 그룹핑
    grouped: dict[str, list] = defaultdict(list)
    for s in sessions:
        dt = s.updated_at or s.started_at
        if not dt:
            continue
        date_str = dt.date().isoformat()
        novel = novels.get(s.id)
        world = worlds.get(s.world_id)
        author_str = AUTHOR_ID_MAP.get(s.author_id) if s.author_id else None
        grouped[date_str].append({
            "session_id": str(s.id),
            "title": novel.title if novel else (world.title if world else "제목 없음"),
            "status": s.status.value,
            "author_id": author_str,
            "type": "writing",
            "chars_added": len(novel.content or "") if novel else 0,
        })

    return [
        {"date": date, "activities": items}
        for date, items in sorted(grouped.items(), reverse=True)
    ]


# ── 6. 문장 보관함 목록 ─────────────────────────────────────────
@router.get("/sentences")
async def get_sentences(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    rows = (await db.execute(
        select(SavedSentence)
        .where(SavedSentence.user_id == user.id)
        .order_by(SavedSentence.created_at.desc())
    )).scalars().all()

    # session title 조회
    session_ids = [r.session_id for r in rows if r.session_id]
    novels_map = {}
    worlds_map = {}
    if session_ids:
        _sessions = (await db.execute(
            select(Session).where(Session.id.in_(session_ids))
        )).scalars().all()
        _novel_list = (await db.execute(
            select(Novel).where(Novel.session_id.in_(session_ids))
        )).scalars().all()
        novels_map = {n.session_id: n for n in _novel_list}
        world_ids = [s.world_id for s in _sessions]
        _world_list = (await db.execute(
            select(World).where(World.id.in_(world_ids))
        )).scalars().all()
        worlds_map = {w.id: w for w in _world_list}
        sessions_map = {s.id: s for s in _sessions}
    else:
        sessions_map = {}

    result = []
    for r in rows:
        title = None
        if r.session_id:
            sess = sessions_map.get(r.session_id)
            nov = novels_map.get(r.session_id)
            wld = worlds_map.get(sess.world_id) if sess else None
            title = nov.title if nov else (wld.title if wld else None)
        result.append({
            "id": str(r.id),
            "content": r.content,
            "label": r.label,
            "session_id": str(r.session_id) if r.session_id else None,
            "session_title": title,
            "created_at": r.created_at.isoformat(),
        })
    return result


# ── 7. 문장 저장 ────────────────────────────────────────────────
class SentenceCreate(BaseModel):
    user_id: str
    content: str
    label: str | None = None
    session_id: str | None = None


@router.post("/sentences", status_code=201)
async def save_sentence(
    body: SentenceCreate,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(body.user_id, db)

    sid = None
    if body.session_id:
        try:
            sid = uuid.UUID(body.session_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="유효하지 않은 session_id")

    sentence = SavedSentence(
        user_id=user.id,
        session_id=sid,
        content=body.content.strip(),
        label=body.label,
    )
    db.add(sentence)
    await db.flush()
    await db.refresh(sentence)

    return {
        "id": str(sentence.id),
        "content": sentence.content,
        "label": sentence.label,
        "session_id": str(sentence.session_id) if sentence.session_id else None,
        "created_at": sentence.created_at.isoformat(),
    }


# ── 8. 문장 삭제 ────────────────────────────────────────────────
@router.delete("/sentences/{sentence_id}", status_code=204)
async def delete_sentence(
    sentence_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)
    try:
        sid = uuid.UUID(sentence_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="유효하지 않은 sentence_id")

    sentence = (await db.execute(
        select(SavedSentence).where(
            SavedSentence.id == sid,
            SavedSentence.user_id == user.id,
        )
    )).scalar_one_or_none()

    if not sentence:
        raise HTTPException(status_code=404, detail="문장을 찾을 수 없습니다.")

    await db.delete(sentence)
    await db.commit()


# ── 9. AI 작가 기록 (Phase 2) ───────────────────────────────────
@router.get("/author-records")
async def get_author_records(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session).where(Session.user_id == user.id)
    )).scalars().all()

    author_session_ids: dict[str, list] = defaultdict(list)
    for s in sessions:
        if s.author_id is not None:
            aid = AUTHOR_ID_MAP.get(s.author_id)
            if aid:
                author_session_ids[aid].append(s.id)

    result = []
    for aid, sids in author_session_ids.items():
        dialogue_count = (await db.execute(
            select(func.count(Dialogue.id)).where(Dialogue.session_id.in_(sids))
        )).scalar_one()

        work_count = len(sids)
        # 별점: 작품 수 기반 (1개=1★, 3개=3★, 5개 이상=5★)
        stars = min(5, max(1, work_count))

        result.append({
            "author_id": aid,
            "name": _AUTHOR_NAMES.get(aid, aid),
            "work_count": work_count,
            "dialogue_count": dialogue_count,
            "stars": stars,
        })

    return sorted(result, key=lambda x: x["work_count"], reverse=True)


# ── 10. 업적 (Phase 2) ──────────────────────────────────────────
@router.get("/achievements")
async def get_achievements(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session).where(Session.user_id == user.id)
    )).scalars().all()

    session_ids = [s.id for s in sessions]

    total_chars = 0
    if session_ids:
        novels = (await db.execute(
            select(Novel).where(Novel.session_id.in_(session_ids))
        )).scalars().all()
        total_chars = sum(len(n.content or "") for n in novels)

    completed_count = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)
    author_counts = Counter(
        AUTHOR_ID_MAP.get(s.author_id) for s in sessions if s.author_id is not None
    )

    total_dialogues = 0
    if session_ids:
        total_dialogues = (await db.execute(
            select(func.count(Dialogue.id)).where(Dialogue.session_id.in_(session_ids))
        )).scalar_one()

    achievements = [
        {"id": "first_work",    "title": "첫 이야기",    "desc": "첫 작품을 시작했어요",          "icon": "📖", "unlocked": len(sessions) >= 1},
        {"id": "first_complete","title": "완결의 맛",    "desc": "첫 작품을 완결했어요",          "icon": "🏆", "unlocked": completed_count >= 1},
        {"id": "chars_10k",     "title": "만자 돌파",    "desc": "총 1만 글자를 작성했어요",      "icon": "✍️", "unlocked": total_chars >= 10_000},
        {"id": "chars_100k",    "title": "십만자 달성",  "desc": "총 10만 글자를 작성했어요",     "icon": "🌟", "unlocked": total_chars >= 100_000},
        {"id": "feedback_10",   "title": "대화의 시작",  "desc": "AI와 10번 이상 대화했어요",     "icon": "💬", "unlocked": total_dialogues >= 10},
        {"id": "feedback_100",  "title": "백번의 대화",  "desc": "AI와 100번 이상 대화했어요",    "icon": "🎯", "unlocked": total_dialogues >= 100},
        {"id": "multi_author",  "title": "다양한 시선",  "desc": "3명 이상의 작가와 협업했어요",  "icon": "🎭", "unlocked": len([a for a in author_counts if author_counts[a] >= 1]) >= 3},
        {"id": "works_5",       "title": "다작 작가",    "desc": "5개 이상의 작품을 시작했어요",  "icon": "📚", "unlocked": len(sessions) >= 5},
    ]
    # 작가별 단골 업적
    for aid, aname in _AUTHOR_NAMES.items():
        achievements.append({
            "id": f"author_{aid}_3",
            "title": f"{aname}의 단골",
            "desc": f"{aname}와 3개 이상 작품을 썼어요",
            "icon": "⭐",
            "unlocked": author_counts.get(aid, 0) >= 3,
        })

    return achievements


# ── 12. 대시보드 ────────────────────────────────────────────────
@router.get("/dashboard")
async def get_dashboard(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)
    now = datetime.now(timezone.utc)

    sessions = (await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
    )).scalars().all()

    if not sessions:
        return {
            "days_since_active": None,
            "resume_work": None,
            "recent_feedback": None,
            "weekly_chars": 0,
            "weekly_goal": 10000,
            "author_shares": [],
        }

    session_ids = [s.id for s in sessions]

    # days_since_active
    last_updated = sessions[0].updated_at
    days_since_active = None
    if last_updated:
        ldt = last_updated.replace(tzinfo=timezone.utc) if last_updated.tzinfo is None else last_updated
        days_since_active = (now - ldt).days

    # resume_work / recent_feedback / weekly_chars
    # ※ 동시 다중 세션(독립 커넥션) 병렬화는 Neon에서 커넥션 establish 경합으로 오히려 느림(실측).
    #   단일 세션 순차로 두되, Novel은 세션 전체분을 한 번에 가져와 latest/weekly 둘 다 커버(2쿼리→1쿼리).
    latest = sessions[0]
    week_ago = now - timedelta(days=7)
    weekly_sids = {
        s.id for s in sessions
        if s.updated_at and (
            s.updated_at.replace(tzinfo=timezone.utc) if s.updated_at.tzinfo is None else s.updated_at
        ) >= week_ago
    }

    novels = (await db.execute(
        select(Novel).where(Novel.session_id.in_(session_ids))
    )).scalars().all()
    latest_novel = next((n for n in novels if n.session_id == latest.id), None)
    weekly_chars = sum(len(n.content or "") for n in novels if n.session_id in weekly_sids)

    latest_world = None
    if latest.world_id:
        latest_world = (await db.execute(
            select(World).where(World.id == latest.world_id)
        )).scalar_one_or_none()
    protagonist = None
    if latest.protagonist_id:
        protagonist = (await db.execute(
            select(Character).where(Character.id == latest.protagonist_id)
        )).scalar_one_or_none()

    author_str = AUTHOR_ID_MAP.get(latest.author_id) if latest.author_id else None
    resume_work = {
        "session_id": str(latest.id),
        "title": latest_novel.title if latest_novel else (latest_world.title if latest_world else "제목 없음"),
        "author_id": author_str,
        "author_name": _AUTHOR_NAMES.get(author_str) if author_str else None,
        "last_modified": latest.updated_at.isoformat() if latest.updated_at else None,
        "char_count": len(latest_novel.content or "") if latest_novel else 0,
        "protagonist_name": protagonist.name if protagonist else None,
    }

    # recent_feedback: 가장 최근 AI(CHARACTER) 대화
    recent_dialogue = (await db.execute(
        select(Dialogue)
        .where(
            Dialogue.session_id.in_(session_ids),
            Dialogue.speaker_type == SpeakerType.CHARACTER,
        )
        .order_by(Dialogue.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    recent_feedback = None
    if recent_dialogue:
        fb_session = next((s for s in sessions if s.id == recent_dialogue.session_id), None)
        fb_author = AUTHOR_ID_MAP.get(fb_session.author_id) if fb_session and fb_session.author_id else None
        raw = recent_dialogue.content
        trimmed = raw[:80].rstrip() + ("…" if len(raw) > 80 else "")
        recent_feedback = {
            "author_name": _AUTHOR_NAMES.get(fb_author, "AI 작가") if fb_author else "AI 작가",
            "content": trimmed,
        }

    # weekly_chars 는 위 novels 한 번 조회에서 이미 계산됨

    # author_shares
    author_counts = Counter(
        AUTHOR_ID_MAP.get(s.author_id) for s in sessions if s.author_id is not None
    )
    total = sum(author_counts.values()) or 1
    author_shares = [
        {
            "author_id": aid,
            "name": _AUTHOR_NAMES.get(aid, aid),
            "ratio": round(cnt / total * 100),
        }
        for aid, cnt in author_counts.most_common()
        if aid
    ]

    return {
        "days_since_active": days_since_active,
        "resume_work": resume_work,
        "recent_feedback": recent_feedback,
        "weekly_chars": weekly_chars,
        "weekly_goal": 10000,
        "author_shares": author_shares,
    }


# ── 11. 창작 통계 (Phase 2) ─────────────────────────────────────
@router.get("/stats")
async def get_stats(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(user_id, db)

    sessions = (await db.execute(
        select(Session).where(Session.user_id == user.id)
    )).scalars().all()

    if not sessions:
        return {
            "total_chars": 0,
            "avg_chars_per_work": 0,
            "most_used_author": None,
            "work_count": 0,
            "completed_count": 0,
        }

    session_ids = [s.id for s in sessions]
    novels = (await db.execute(
        select(Novel).where(Novel.session_id.in_(session_ids))
    )).scalars().all()

    char_counts = [len(n.content or "") for n in novels]
    total_chars = sum(char_counts)
    avg_chars = total_chars // len(char_counts) if char_counts else 0

    author_counts = Counter(
        AUTHOR_ID_MAP.get(s.author_id) for s in sessions if s.author_id is not None
    )
    most_used_entry = author_counts.most_common(1)
    most_used = None
    if most_used_entry and most_used_entry[0][0]:
        aid, cnt = most_used_entry[0]
        most_used = {"author_id": aid, "name": _AUTHOR_NAMES.get(aid, aid), "count": cnt}

    completed_count = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)

    return {
        "total_chars": total_chars,
        "avg_chars_per_work": avg_chars,
        "most_used_author": most_used,
        "work_count": len(sessions),
        "completed_count": completed_count,
    }


# ── 취향 프로필 ──────────────────────────────────────────────────
_TASTE_PROMPT = """\
사용자가 선택한 좋아하는 작품들입니다. 이를 바탕으로 취향 프로파일을 분석해주세요.

{categories_text}

반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):
{{
  "선호장르": "대표 장르나 분위기를 간결하게 (예: '현대 로맨스', '다크 판타지 액션', '감성 성장물')",
  "선호키워드": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}

선호키워드는 선택된 작품들에서 공통적으로 보이는 트로프, 분위기, 주제를 3~5개 추출해주세요. (예: '아이돌', '비밀연애', '집착남', '세계 멸망', '계략과 배신', '평행세계', '압도적 성장')"""

_CATEGORY_KO = {"book": "책", "movie": "영화", "drama": "드라마"}


class TasteSetupRequest(BaseModel):
    user_id: str
    selected_works: list[dict]  # [{id, title, category, tags}]


class TasteProfileResponse(BaseModel):
    selected_works: list[dict]
    taste_profile: dict


@router.get("/taste")
async def get_taste_profile(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TasteProfileResponse:
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return TasteProfileResponse(selected_works=[], taste_profile={})

    row = (await db.execute(
        select(UserTasteProfile).where(UserTasteProfile.user_id == uid)
    )).scalar_one_or_none()

    if not row:
        return TasteProfileResponse(selected_works=[], taste_profile={})
    return TasteProfileResponse(selected_works=row.selected_works or [], taste_profile=row.taste_profile or {})


@router.post("/taste/setup")
async def setup_taste_profile(
    body: TasteSetupRequest,
    db: AsyncSession = Depends(get_db),
) -> TasteProfileResponse:
    try:
        uid = uuid.UUID(body.user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid user_id")

    # 카테고리별 작품 그룹핑
    by_cat: dict[str, list[str]] = {}
    for w in body.selected_works:
        cat = w.get("category", "기타")
        by_cat.setdefault(cat, []).append(w.get("title", ""))

    categories_text = "\n".join(
        f"[{_CATEGORY_KO.get(cat, cat)}]\n" + "\n".join(f"- {t}" for t in titles)
        for cat, titles in by_cat.items()
    )

    taste_profile: dict = {}
    try:
        system_prompt = _TASTE_PROMPT.format(categories_text=categories_text)
        contents = [{"role": "user", "parts": [{"text": "위 작품들을 분석해서 취향 JSON을 반환해주세요."}]}]
        raw = await llm.generate(system_prompt, contents, json_mode=True)
        if raw:
            text = raw if isinstance(raw, str) else json.dumps(raw)
            text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(text)
            if "선호장르" in parsed:
                taste_profile["선호장르"] = str(parsed["선호장르"])
            if "선호키워드" in parsed and isinstance(parsed["선호키워드"], list):
                taste_profile["선호키워드"] = [str(k) for k in parsed["선호키워드"][:6]]
    except Exception as e:
        logger.warning("취향 LLM 분석 실패: %s", e)

    # upsert
    row = (await db.execute(
        select(UserTasteProfile).where(UserTasteProfile.user_id == uid)
    )).scalar_one_or_none()

    if row:
        row.selected_works = body.selected_works
        row.taste_profile = taste_profile
    else:
        row = UserTasteProfile(user_id=uid, selected_works=body.selected_works, taste_profile=taste_profile)
        db.add(row)

    await db.commit()
    logger.info("취향 프로필 저장 - user=%s works=%d", body.user_id, len(body.selected_works))
    return TasteProfileResponse(selected_works=body.selected_works, taste_profile=taste_profile)
