"""오탈자/맞춤법 교정 코어 (검출 + 검증).

설계 원칙:
- **판정은 LLM이 아니라 F-QC-02(네이버 맞춤법기)** 가 한다 → 환각(멀쩡한 걸 틀렸다고) 차단.
- F-QC-02는 '교정문(문자열)'만 주므로, **원문 vs 교정문 char-level diff** 로 실제 바뀐 구간만 오류쌍으로 추출.
- confusion 소사전은 '검출'이 아니라 **유형 분류/코칭 라벨**용 (되/돼·안/않 등 자주 헷갈리는 것).
- 자동 수정은 하지 않는다 — 호출부가 '제안'만 하고 최종 결정은 사용자(작가가 일부러 쓴 사투리/문체 보호).

반환 오류쌍: {"original": 틀린어절, "corrected": 맞는어절, "type": "맞춤법|띄어쓰기|오타|되/돼|..."}
"""
from __future__ import annotations

import asyncio
import difflib
import logging
import re
import time

from f_qc_02_spell_checker import check_korean_grammar_status

logger = logging.getLogger(__name__)

# 자모(ㅋㅋ·ㅠㅠ·ㄷㄷ)·늘임(좋아아아·ㅋㅋㅋ)은 오타가 아니라 감정 표현 → 교정 제외.
_JAMO_ONLY = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ]+$")   # 순수 자모만으로 된 어절
_REPEAT3 = re.compile(r"(.)\1\1")              # 같은 글자 3연속(늘임)

# 문장부호(. ? ! …) 뒤 한 칸 띄우고 여는 따옴표가 오는 건 정상 표기.
# 네이버가 그 공백을 지우라고 해도(`옮겼다. "이제` → `옮겼다."이제`) 오탐 → 교정 제외.
_PUNCT_QUOTE_SPACE = re.compile(r'([.?!…])\s+(["\'“‘「『])')


def _is_stylistic(word: str) -> bool:
    """ㅋㅋ·ㅠㅠ 같은 자모, '좋아아아' 같은 늘임은 의도된 표현 → 맞춤법 제외."""
    w = (word or "").strip()
    return bool(w) and bool(_JAMO_ONLY.match(w) or _REPEAT3.search(w))


def _is_punct_quote_fp(original: str, corrected: str) -> bool:
    """오류쌍의 차이가 '문장부호 뒤 공백 + 여는 따옴표'의 공백을 없애는 것뿐이면 오탐.

    온점/물음표/느낌표 뒤 한 칸 띄우고 따옴표가 오는 건 자연스러운 표기라
    검사기가 붙이라고 제안해도 교정에서 제외한다(공백 외 글자 변화가 있으면 적용 안 함).
    """
    if original.replace(" ", "") != corrected.replace(" ", ""):
        return False  # 글자 자체가 바뀐 건 여기서 거르지 않음(순수 띄어쓰기 차이만 대상)
    return _PUNCT_QUOTE_SPACE.sub(r"\1\2", original) == corrected

# 자주 틀리는 한국어 혼동쌍 → 유형 라벨. (검출이 아니라 분류·코칭용)
# key는 '틀린 표기에 포함되는 조각', value=(올바른 예, 유형 라벨).
CONFUSION: dict[str, tuple[str, str]] = {
    "됬": ("됐", "되/돼"),
    "되요": ("돼요", "되/돼"),
    "되써": ("됐어", "되/돼"),
    "안되": ("안 돼", "되/돼"),
    "않돼": ("안 돼", "안/않"),
    "어떻해": ("어떡해", "어떻게/어떡해"),
    "어떡게": ("어떻게", "어떻게/어떡해"),
    "왠일": ("웬일", "왠/웬"),
    "웬지": ("왠지", "왠/웬"),
    "몇일": ("며칠", "며칠"),
    "금새": ("금세", "금세/금새"),
    "오랫만": ("오랜만", "오랜만/오랫만"),
    "희안": ("희한", "희한"),
    "역활": ("역할", "역할/역활"),
    "낳는": ("낫는", "낫다/낳다"),
    "낳아": ("나아", "낫다/낳다"),
    "들어나": ("드러나", "드러나다"),
    "할께": ("할게", "ㄹ게/ㄹ께"),
    "갈께": ("갈게", "ㄹ게/ㄹ께"),
    "로써": ("로서", "로서/로써"),
    "던지": ("든지", "든지/던지"),
    "맞추": ("맞히", "맞추다/맞히다"),
    "바램": ("바람", "바람/바램"),
}


def _touches_protected(word: str, protected: set[str] | None) -> bool:
    """오류 어절에 보호어(등장인물·세계관 고유명사)가 닿으면 True → 교정 제외.

    일반 맞춤법기는 창작 고유명사('카이렌')를 모르고 쪼개거나('카이 레인') 바꾼다.
    어절에서 조사가 붙어도(카이렌'의') 보호어가 부분문자열이면 잡아낸다.
    """
    if not protected:
        return False
    flat = word.replace(" ", "")
    return any(p and (p in word or p in flat) for p in protected)


def _classify(original: str, corrected: str) -> str:
    """오류 유형 추정. 띄어쓰기 > 혼동쌍 > 맞춤법 순."""
    if original.replace(" ", "") == corrected.replace(" ", ""):
        return "띄어쓰기"
    for wrong, (_right, kind) in CONFUSION.items():
        if wrong in original:
            return kind
    return "맞춤법"


def _diff_errors(original: str, corrected: str, protected: set[str] | None = None) -> list[dict]:
    """원문 vs 교정문 **어절(공백 분리) 단위 diff** → 바뀐 어절을 통째로 오류쌍으로 반환.

    어절 단위라 `마춤법 → 맞춤법`처럼 단어 전체로 읽히고, 네이버가 띄어쓰기를 바꿔
    한 어절이 둘로 갈려도(`안되요 → 안 돼요`) 자연스럽게 묶인다.
    protected: 등장인물·세계관 고유명사 → 닿은 오류쌍은 제외(창작 명사 보호).
    """
    ow, cw = original.split(), corrected.split()
    sm = difflib.SequenceMatcher(None, ow, cw, autojunk=False)
    errors: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        o_words, c_words = ow[i1:i2], cw[j1:j2]
        if tag == "replace" and len(o_words) == len(c_words):
            # 어절 수가 1:1 → 단어별 개별 오류로 분리 (연속 교정도 따로따로)
            for o_w, c_w in zip(o_words, c_words):
                if o_w != c_w:
                    errors.append({"original": o_w, "corrected": c_w, "type": _classify(o_w, c_w)})
        else:
            # 어절 수가 다름(띄어쓰기로 갈림·합쳐짐) → 묶어서 한 오류로
            o, c = " ".join(o_words).strip(), " ".join(c_words).strip()
            if o and c and o != c:
                errors.append({"original": o, "corrected": c, "type": _classify(o, c)})
    # 자모·늘임(ㅋㅋ·좋아아아)은 표현이므로 항상 제외
    errors = [e for e in errors if not _is_stylistic(e["original"])]
    # 문장부호 뒤 공백+따옴표(`다. "이제`)는 정상 표기 → 공백 제거 제안은 오탐이라 제외
    errors = [e for e in errors if not _is_punct_quote_fp(e["original"], e["corrected"])]
    if protected:
        # 등장인물·세계관 고유명사가 닿은 오류쌍은 버린다(일반 맞춤법기가 모르는 창작 명사)
        errors = [e for e in errors if not _touches_protected(e["original"], protected)]
    return errors


async def proofread(text: str, protected: set[str] | None = None) -> tuple[list[dict], bool]:
    """**(오류쌍 리스트, checker_ok)** 를 반환.

    protected: 등장인물·세계관 고유명사 집합 → 그 명사가 닿은 오류는 제외(창작 명사 보호).

    - checker_ok=False = **네이버 검사기가 못 돈 것**(변경/차단/네트워크). 이때도 errors=[]지만,
      "검사했는데 깨끗함"과 구분돼서 호출부가 '조용히 안 됨'을 알 수 있다(가드의 핵심).
    - F-QC-02는 동기(requests) → 이벤트 루프 안 막게 thread로 실행.
    """
    text = (text or "").strip()
    if not text:
        return [], True
    try:
        corrected, ok = await asyncio.to_thread(check_korean_grammar_status, text)
    except Exception as e:  # noqa: BLE001 - 예외는 '검사 실패'로 흡수(흐름 안 막음)
        logger.warning("맞춤법 검사 실패(교정 생략): %s", e)
        return [], False
    if not ok:
        logger.warning("⚠️ 맞춤법 검사기 동작 실패 — 네이버 변경/차단 의심(교정 미수행, errors=[]로 오인 주의)")
        return [], False
    if not corrected or corrected.strip() == text:
        return [], True
    return _diff_errors(text, corrected, protected), True


# ── 개인 오답노트(error_profile) 누적/매칭 ────────────────────
# profile 형태: { "<틀린표기>": {"corrected": str, "type": str, "count": int} }

def update_profile(profile: dict | None, errors: list[dict]) -> tuple[dict, list[dict]]:
    """errors를 profile에 누적하고, 각 error에 frequent 플래그(이전 count>=2)를 붙여 반환.

    반환: (갱신된 profile, frequent 플래그 달린 errors)
    """
    profile = dict(profile or {})
    flagged: list[dict] = []
    for err in errors:
        key = err["original"]
        entry = profile.get(key) or {"corrected": err["corrected"], "type": err["type"], "count": 0}
        prev = entry.get("count", 0)
        entry["count"] = prev + 1
        entry["corrected"] = err["corrected"]
        entry["type"] = err["type"]
        entry["last"] = time.time()   # 최신순 정렬용(마지막으로 틀린 시각)
        profile[key] = entry
        flagged.append({**err, "frequent": prev >= 2, "count": entry["count"]})
    return profile, flagged


def notebook(profile: dict | None, limit: int = 50) -> list[dict]:
    """error_profile → 자주 틀리는 순으로 정렬된 오답노트 리스트."""
    items = [
        {"original": k, "corrected": v.get("corrected", ""), "type": v.get("type", ""),
         "count": v.get("count", 0), "last": v.get("last", 0)}
        for k, v in (profile or {}).items()
    ]
    items.sort(key=lambda x: x["count"], reverse=True)
    return items[:limit]


def remove_entry(profile: dict | None, original: str) -> dict:
    """오답노트에서 한 항목(original 키)을 제거한 새 profile 반환."""
    profile = dict(profile or {})
    profile.pop(original, None)
    return profile
