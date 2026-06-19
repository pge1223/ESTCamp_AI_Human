"""
services/world_tag_classifier.py
---------------------------------
F-WD-06 세계관 태그 자동분류 (하이브리드).

전략:
    1. 1차 키워드 필터 — 세계관 텍스트에서 카테고리 후보 압축
       (120개 전체 주입 않음 → 토큰 절약)
    2. LLM closed-set 분류 — 후보 30~40개만 주고 "해당되는 것 다 골라"
    3. DB 저장 (World.tags JSON 컬럼)
    4. 프론트에서 사용자가 추가/삭제 편집 가능

파일 위치:
    data/world_tags.json        — 마스터 라벨 사전 (정적 참조)
    backend/app/services/world_tag_classifier.py — 이 파일

사용 예시:
    result = await classify_world_tags(world_text="...")
    print(result.tags)           # 분류된 태그 리스트 (DB 저장용)
    print(result.context_block)  # 프롬프트/RAG 주입용 블록
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# ── 마스터 라벨 사전 로드 ──────────────────────────────────────

_TAG_FILE = Path(__file__).parent.parent.parent.parent / "data" / "world_tags.json"


def _load_fixed_tags() -> dict[str, list[str]]:
    try:
        with open(_TAG_FILE, encoding="utf-8") as f:
            return json.load(f)["categories"]
    except FileNotFoundError:
        logger.warning("[WorldTagClassifier] world_tags.json 없음")
        return {}


_FIXED_TAGS: dict[str, list[str]] = _load_fixed_tags()
_ALL_FLAT: list[str] = [t for tags in _FIXED_TAGS.values() for t in tags]


# ── 1차 키워드 필터 ────────────────────────────────────────────
# 카테고리별 트리거 키워드 — 매칭되면 해당 카테고리 후보에 포함

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "주장르":    ["로맨스", "호러", "공포", "추리", "범죄", "판타지", "마법", "SF", "우주",
                  "무협", "역사", "시대", "일상", "에세이", "스릴러", "액션", "BL", "GL"],
    "세부장르":  ["이세계", "회귀", "빙의", "헌터", "게임", "던전", "궁중", "아포칼립스",
                  "사이버", "스팀", "학원", "학교", "직장", "의사", "병원", "법정", "스포츠", "군대"],
    "분위기·톤": ["어둡", "무거", "밝", "경쾌", "잔잔", "따뜻", "긴장", "스릴", "몽환",
                  "쓸쓸", "고독", "유머", "웃기", "감동", "잔혹", "냉혹", "서정", "신비", "퇴폐"],
    "시대·배경": ["현대", "조선", "고려", "삼국", "중세", "19세기", "20세기", "미래", "우주",
                  "왕국", "이세계", "포스트", "근대", "일제", "개화"],
    "공간·배경": ["도시", "학교", "직장", "회사", "병원", "궁궐", "저택", "던전", "바다",
                  "숲", "우주선", "폐허", "황무지", "가상현실", "마을", "군부대", "감옥"],
    "서사구조":  ["성장", "복수", "연애", "삼각", "우정", "앙상블", "서바이벌", "탐정",
                  "수사", "정치", "음모", "전쟁", "여행", "모험", "금지", "재회", "신분", "계약",
                  "스승", "제자", "라이벌", "구원"],
    "인물구도":  ["주인공", "먼치킨", "성장형", "악역", "빙의", "전생", "괴물", "신", "AI"],
    "감정·테마": ["사랑", "집착", "상실", "슬픔", "배신", "용서", "정체성", "가족", "계급",
                  "생존", "복수", "화해", "자유", "구속", "믿음", "희생", "욕망", "타락",
                  "운명", "선택", "고독", "연대", "각성"],
    "결말유형":  ["해피엔딩", "배드엔딩", "비극", "열린결말", "반전"],
    "서술방식":  ["1인칭", "3인칭", "전지적", "관찰자", "일기", "편지", "회상", "액자",
                  "비선형", "실시간"],
    "히든변수":  ["반전", "복선", "비밀", "숨겨진", "예언", "운명", "저주", "금기", "이중생활",
                  "트라우마", "기억상실", "루프", "회귀", "죽음"],
}


def _filter_candidate_tags(world_text: str) -> list[str]:
    """
    세계관 텍스트 키워드 기반으로 관련 카테고리 후보만 추출.
    매칭 없는 카테고리는 제외 → 토큰 절약.
    """
    text = world_text.lower()
    candidates: list[str] = []
    matched_categories: set[str] = set()

    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched_categories.add(category)

    # 매칭된 카테고리 태그 추가
    for category in matched_categories:
        candidates.extend(_FIXED_TAGS.get(category, []))

    # 매칭 카테고리 없으면 전체 반환 (폴백)
    if not candidates:
        logger.debug("[1차필터] 매칭 없음 — 전체 태그 사용")
        return _ALL_FLAT

    logger.debug("[1차필터] 매칭 카테고리=%s, 후보=%d개", matched_categories, len(candidates))
    return candidates


# ── 분류 프롬프트 ──────────────────────────────────────────────

_CLASSIFY_PROMPT = """\
아래 소설 세계관을 읽고 [태그 목록]에서 해당되는 태그를 모두 골라주세요.

[세계관]
{world_text}

[태그 목록]
{tag_list}

[규칙]
- 목록에 있는 태그만 선택 (새로운 태그 만들지 않음)
- 해당되는 것 전부 선택 (최소 5개 이상)
- JSON 배열로만 출력 (설명 없이)

출력 예시:
["로맨스", "현대 한국", "신분차이", "삼각관계", "어둡고무거움"]
"""


# ── 결과 데이터클래스 ──────────────────────────────────────────

@dataclass
class WorldTagResult:
    tags: list[str]          # 분류된 태그 (DB 저장용, 사용자 편집 가능)
    candidate_count: int     # 1차 필터 후보 수 (모니터링용)
    world_text: str

    @property
    def context_block(self) -> str:
        """프롬프트/RAG 주입용 블록."""
        if not self.tags:
            return ""
        return f"[세계관 태그]\n{', '.join(self.tags)}"


# ── 메인 분류 함수 ─────────────────────────────────────────────

async def classify_world_tags(
    world_text: str,
    model_name: str = "gemini-2.5-flash",
) -> WorldTagResult:
    """
    세계관 텍스트 → 멀티라벨 태그 자동 분류.

    Args:
        world_text: 세계관 요약 + 배경 + 등장인물 텍스트 (폼 입력 조합)

    Returns:
        WorldTagResult.tags → DB(World.tags)에 저장
        사용자가 프론트에서 추가/삭제로 편집 가능
    """
    if not world_text.strip():
        return WorldTagResult(tags=[], candidate_count=0, world_text=world_text)

    # 1차 필터 — 후보 압축
    candidates = _filter_candidate_tags(world_text)
    tag_list = "\n".join(f"- {t}" for t in candidates)

    prompt = _CLASSIFY_PROMPT.format(
        world_text=world_text[:1500],
        tag_list=tag_list,
    )

    try:
        model = genai.GenerativeModel(model_name)
        resp = await asyncio.to_thread(
            model.generate_content,
            [{"role": "user", "parts": [{"text": prompt}]}],
        )
        raw = resp.text.strip()

        # JSON 파싱 방어
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        generated: list[str] = json.loads(raw.strip())

    except Exception as e:
        logger.error("[WorldTagClassifier] LLM 호출 실패: %s", e)
        return WorldTagResult(tags=[], candidate_count=len(candidates), world_text=world_text)

    # 고정 리스트에 있는 태그만 통과 (노이즈 방어)
    valid_set = set(_ALL_FLAT)
    tags = [t for t in generated if t in valid_set]

    logger.info("[WorldTagClassifier] 완료 — 후보=%d개, 선택=%d개", len(candidates), len(tags))

    return WorldTagResult(
        tags=tags,
        candidate_count=len(candidates),
        world_text=world_text,
    )


# ── CLI 테스트 ─────────────────────────────────────────────────

async def _test():
    sample = """
    2019년 서울. 폐공장 지구 한편에 자리한 탐정 사무소.
    주인공 이수아(28)는 3년 전 남동생의 실종 사건을 혼자 추적 중이다.
    어느 날 의뢰인으로 찾아온 강민준은 수아의 동생과 관련된 비밀을 알고 있다.
    두 사람은 서로를 의심하면서도 협력해야 한다.
    """

    result = await classify_world_tags(sample)
    print(f"후보 {result.candidate_count}개 중 {len(result.tags)}개 선택")
    print("태그:", result.tags)
    print("\n주입용 블록:")
    print(result.context_block)


if __name__ == "__main__":
    asyncio.run(_test())
