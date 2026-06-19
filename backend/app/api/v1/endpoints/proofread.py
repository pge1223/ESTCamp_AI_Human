"""오탈자/맞춤법 교정 엔드포인트 (F-QC-02 기반).

- POST /chats/{chat_id}/proofread     : 문장 검사 → 오류쌍 + 자주틀림 플래그 + (선택)작가 톤 메모
- GET  /users/{user_id}/error-notebook : 개인 오답노트(자주 틀리는 순)

검출/검증은 services.proofread(F-QC-02 정답지 + diff), 자동 수정 X(제안만).
"""
import uuid
import json
import re
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import Session
from app.models.user import User
from app.models.character import Character
from app.models.world import World
from app.services import proofread as pf
from app.services import llm

router = APIRouter()
logger = logging.getLogger(__name__)

# 작가별 톤 — 교정 메모를 '빨간펜'이 아니라 '협업 작가의 여백 메모'처럼 띄우기 위함
AUTHOR_TONE = {
    "baekya":     "백야 — 호러/미스터리 작가. 담담하고 건조한 반말(빈정대지 않음).",
    "charoun":    "차로운 — 본격 추리 작가. 분석적이고 또박또박한 존댓말.",
    "hanyeoreum": "한여름 — 로맨스 작가. 다정하고 살가운 말투.",
    "kimdohyeon": "김도현 — 일상/에세이 작가. 편안하고 따뜻한 말투.",
}


class ProofreadRequest(BaseModel):
    text: str
    character_id: str = "baekya"
    persona_memo: bool = True   # 작가 톤 한 줄 메모 생성 여부


async def _resolve_user(chat_id: str, db: AsyncSession) -> User | None:
    """chat_id(=session_id) → 세션 → 작성 유저. 익명/유효X면 None."""
    try:
        sid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return None
    session = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
    if session is None or not session.user_id:
        return None
    return (await db.execute(select(User).where(User.id == session.user_id))).scalar_one_or_none()


async def _extract_glossary(world: World, char_names: list[str]) -> list[str]:
    """세계관 자유서술(배경·규칙 등)에서 **창작 고유명사**를 LLM으로 1회 추출.

    실패하면 [] 반환(빈 추출로 캐시 → 재시도 안 함). 판정이 아니라 '용어 시드'라
    proofread의 'LLM은 판정 안 함' 원칙과 별개(메모와 동일 층).
    """
    parts = [p for p in (world.title, world.setting, world.rules, world.description) if p]
    if not parts:
        return []
    body = "\n".join(parts)
    if char_names:
        body += "\n등장인물: " + ", ".join(char_names)
    system = (
        "너는 창작 세계관 텍스트에서 '고유명사'만 뽑는 추출기다.\n"
        "- 대상: 지명·국가·세력·조직·종족·아이템·기술/마법 등 표준 국어사전에 없는 창작 명사.\n"
        "- 제외: 일반 명사·동사·형용사·흔한 단어, 한 글자.\n"
        '- 반드시 JSON 문자열 배열로만 답한다. 예: ["아르카디아","그림자 길드"]'
    )
    prompt = f"[세계관]\n{body}\n\n위에서 고유명사만 JSON 배열로."
    try:
        raw = await llm.generate(system, [{"role": "user", "parts": [{"text": prompt}]}])
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
        terms = json.loads(raw)
        return [t.strip() for t in terms if isinstance(t, str) and len(t.strip()) >= 2][:50]
    except Exception as e:  # noqa: BLE001 - 추출 실패는 교정을 막지 않음
        logger.warning("세계관 용어집 추출 실패(빈 목록 캐시): %s", e)
        return []


async def _protected_terms(chat_id: str, db: AsyncSession) -> set[str]:
    """세션의 등장인물 이름 + 세계관 제목 + **용어집(glossary)** 을 '보호어'로 모은다.

    일반 맞춤법기가 모르는 창작 고유명사를 오류로 잡지 않게 한다.
    glossary가 None이면 최초 1회 LLM 추출 → 캐시(이후 재사용). '넘기기'로도 누적됨.
    조사가 붙은 어절도 부분문자열로 걸리도록 띄어쓰기 제거형도 함께 넣는다.
    """
    try:
        sid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return set()
    session = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
    if session is None:
        return set()
    terms: set[str] = set()

    def _add(raw: str | None):
        n = (raw or "").strip()
        if len(n) >= 2:
            terms.add(n)
            terms.add(n.replace(" ", ""))

    chars = (await db.execute(
        select(Character).where(Character.world_id == session.world_id)
    )).scalars().all()
    char_names = [c.name for c in chars if c.name]
    for c in chars:
        _add(c.name)

    world = (await db.execute(select(World).where(World.id == session.world_id))).scalar_one_or_none()
    if world is not None:
        _add(world.title)
        if world.glossary is None:   # 최초 1회 LLM 추출 → 캐시
            world.glossary = await _extract_glossary(world, char_names)
            await db.commit()
        for g in (world.glossary or []):
            _add(g)

    return {t for t in terms if len(t) >= 2}


async def _author_memo(character_id: str, errors: list[dict]) -> str:
    """작가 페르소나 톤으로 교정을 '여백 메모' 한 줄로. 오류없음/실패 시 ''."""
    if not errors:
        return ""
    tone = AUTHOR_TONE.get(character_id, AUTHOR_TONE["baekya"])
    pairs = ", ".join(f"{e['original']}→{e['corrected']}" for e in errors[:5])
    system = (
        f"너는 소설 협업 작가다. 페르소나: {tone}\n"
        "사용자(주인공)가 방금 쓴 문장의 맞춤법을 네가 '여백에 메모해주듯' 한 줄로 짚는다.\n"
        "- 잔소리·훈계 금지, 네 작가 말투로 짧고 자연스럽게 (빨간펜 선생님 X, 협업 작가 O)\n"
        "- 절대 사용자를 놀리거나 비꼬거나 능력을 평가하지 말 것. '~라도 하나?' 같은 조롱·비아냥·면박 금지. 글자에 대한 가벼운 코멘트일 뿐 사람 평가가 아니다.\n"
        "- 맞춤법 용어 나열 금지. 딱 한 문장.\n"
        "- 반드시 자연스러운 한국어로만 쓴다. 외국어 단어·한자(自然 등) 절대 섞지 말 것."
    )
    prompt = f"[교정 목록] {pairs}\n위를 네 말투로 한 줄 메모로."
    try:
        text = await llm.generate(system, [{"role": "user", "parts": [{"text": prompt}]}])
        return (text or "").strip().strip('"')
    except Exception as e:  # noqa: BLE001 - 메모 실패는 교정 자체를 막지 않음
        logger.warning("작가 교정 메모 생성 실패: %s", e)
        return ""


@router.post("/chats/{chat_id}/proofread")
async def proofread_chat(
    chat_id: str,
    body: ProofreadRequest,
    db: AsyncSession = Depends(get_db),
):
    """사용자 문장 맞춤법 검사 → 오류쌍(+자주틀림) + 작가 톤 메모.

    - 판정은 F-QC-02(네이버) → diff. LLM은 메모 표현만(환각 차단).
    - 개인 error_profile 누적 → 같은 실수 재등장 시 frequent=True.
    - **자동 수정하지 않는다** — 프론트는 '제안'만 표시하고 적용/넘기기는 사용자가.
    """
    protected = await _protected_terms(chat_id, db)   # 등장인물·세계관 고유명사 보호
    errors, checker_ok = await pf.proofread(body.text, protected)

    flagged = [{**e, "frequent": False, "count": 1} for e in errors]
    user = await _resolve_user(chat_id, db)
    if user is not None and errors:
        new_profile, flagged = pf.update_profile(user.error_profile, errors)
        user.error_profile = new_profile
        await db.commit()

    memo = await _author_memo(body.character_id, errors) if body.persona_memo else ""
    # checker_ok=False = 네이버 맞춤법기가 동작 못 함 → 프론트는 errors=[]를 '깨끗함'으로 오인하면 안 됨
    return {"errors": flagged, "memo": memo, "count": len(flagged), "checker_ok": checker_ok}


@router.get("/users/{user_id}/error-notebook")
async def error_notebook(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """개인 오답노트 — 자주 틀리는 순으로 정렬."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return {"notebook": pf.notebook(user.error_profile)}


class ErrorEntryDelete(BaseModel):
    original: str


@router.delete("/users/{user_id}/error-notebook")
async def delete_error_entry(
    user_id: uuid.UUID, body: ErrorEntryDelete, db: AsyncSession = Depends(get_db)
):
    """오답노트 항목 1개 삭제(original 키 기준). 갱신된 노트를 돌려준다."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    user.error_profile = pf.remove_entry(user.error_profile, body.original)
    await db.commit()
    return {"notebook": pf.notebook(user.error_profile)}


@router.get("/chats/{chat_id}/error-warmup")
async def error_warmup(chat_id: str, limit: int = 3, db: AsyncSession = Depends(get_db)):
    """능동 경고 — 글쓰기 진입 시 '자주 틀리는 것' 미리 보기.

    반응형(틀린 뒤 교정) → 예측형(틀리기 전 제시) 전환의 1단계.
    이미 2회 이상 틀린 표기만 골라 상위 N개를 돌려준다(처음 틀린 건 잔소리 X).
    LLM 미사용 — error_profile 누적 데이터 그대로라 환각·지연·비용 0.
    """
    user = await _resolve_user(chat_id, db)
    if user is None:
        return {"items": [], "count": 0}
    frequent = [it for it in pf.notebook(user.error_profile) if it.get("count", 0) >= 2]
    return {"items": frequent[: max(1, limit)], "count": len(frequent)}


# ── 세계관 용어집(맞춤법 보호 사전) ─────────────────────────────
class GlossaryAddRequest(BaseModel):
    term: str


async def _resolve_world(chat_id: str, db: AsyncSession) -> World | None:
    """chat_id(=session_id) → 세션 → 세계관."""
    try:
        sid = uuid.UUID(chat_id)
    except (ValueError, TypeError):
        return None
    session = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
    if session is None:
        return None
    return (await db.execute(select(World).where(World.id == session.world_id))).scalar_one_or_none()


@router.get("/chats/{chat_id}/glossary")
async def get_glossary(chat_id: str, db: AsyncSession = Depends(get_db)):
    """세계관 보호 용어집 조회(자동 추출 + 넘기기 누적)."""
    world = await _resolve_world(chat_id, db)
    if world is None:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    return {"glossary": world.glossary or []}


@router.post("/chats/{chat_id}/glossary")
async def add_glossary_term(chat_id: str, body: GlossaryAddRequest, db: AsyncSession = Depends(get_db)):
    """'넘기기' → 그 단어를 보호 용어집에 영구 추가(다음 교정부터 제외)."""
    term = (body.term or "").strip()
    if not term:
        raise HTTPException(status_code=400, detail="빈 용어입니다.")
    world = await _resolve_world(chat_id, db)
    if world is None:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    glossary = list(world.glossary or [])
    if term not in glossary:
        glossary.append(term)
        world.glossary = glossary
        await db.commit()
    return {"glossary": glossary}


@router.delete("/chats/{chat_id}/glossary")
async def remove_glossary_term(chat_id: str, term: str, db: AsyncSession = Depends(get_db)):
    """용어집에서 단어 제거(자동 추출이 과보호했을 때 escape). `?term=...`"""
    world = await _resolve_world(chat_id, db)
    if world is None:
        raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")
    glossary = [g for g in (world.glossary or []) if g != term]
    world.glossary = glossary
    await db.commit()
    return {"glossary": glossary}
