"""소설 품질 평가 (LLM-as-judge) — F-EV-06 근거 리포트의 측정 도구.

세계관·작가 성향을 기준으로 소설을 4개 축(세계관 일관성·캐릭터 일관성·문체 뚜렷함·
완성도)에서 1~5점으로 채점한다. "맨손 작성 vs 우리 서비스" 정량 비교의 측정부.

채점 루브릭(프롬프트)은 동완님이 튜닝할 수 있게 상수로 분리.
"""
import re
import json
import logging

from app.services import llm

logger = logging.getLogger(__name__)

_DIMS = ["world_consistency", "character_consistency", "style_distinct", "completeness"]
_DIM_LABEL = {
    "world_consistency": "세계관 일관성",
    "character_consistency": "캐릭터 일관성",
    "style_distinct": "작가 문체 뚜렷함",
    "completeness": "완성도",
}

EVAL_SYSTEM = """\
[소설 품질 평가자]
[세계관]과 [작가 성향]을 기준으로 [소설]을 냉정하게 평가한다.

[채점 기준 — 각 항목 1~5점 정수]

world_consistency (세계관 일관성)
5: 시간·장소·규칙·인물 관계가 설정과 완전히 일치
4: 사소한 묘사 차이만 있고 핵심 설정은 유지
3: 설정과 어긋나는 부분이 1~2개 있지만 흐름은 유지
2: 중요한 설정 충돌이 있어 몰입이 깨짐
1: 세계관과 무관하거나 설정을 정면으로 위반

character_consistency (캐릭터 일관성)
5: 말투·행동·반응이 설정한 성격과 완전히 일치
4: 대부분 일관성 있고 이탈이 1회 이하
3: 성격이 희미하게 드러나거나 이탈이 2~3회
2: 성격이 자주 흔들려 같은 인물로 느껴지지 않음
1: 성격 설정을 전혀 반영하지 않음

style_distinct (작가 문체 구분도)
5: 해당 작가가 아니면 쓸 수 없는 문장. 다른 3명과 혼동 불가
4: 작가 특성이 뚜렷하고 장르 톤이 명확
3: 일반적인 소설 문체. 작가 개성이 약하게 느껴짐
2: 다른 작가와 혼동될 수 있는 수준
1: 어떤 작가인지 전혀 구분 안 됨

completeness (장면 완성도)
5: 장면의 흐름·묘사·감정선이 모두 갖춰짐. 읽는 맛이 있음
4: 대부분 완성도 있고 빠진 요소가 1개 이하
3: 흐름은 있지만 묘사가 얕거나 감정선이 약함
2: 장면이 단편적이고 연결이 부자연스러움
1: 미완성 수준. 내용이 너무 짧거나 끊김

[목표 기준]
- character_consistency 평균 4.0 이상
- style_distinct 평균 4.0 이상 (코사인 유사도 < 0.6 대응)

후하게 주지 말고 근거 있게 채점한다.
반드시 valid JSON만 출력:
{
  "world_consistency": 4,
  "character_consistency": 4,
  "style_distinct": 3,
  "completeness": 4,
  "comment": "한 줄 총평",
  "style_weakness": "문체가 약한 이유 한 줄 (style_distinct < 4 일 때만)"
}
"""

def _empty(comment: str = "평가 실패") -> dict:
    out = {k: 0 for k in _DIMS}
    out["comment"] = comment
    out["total"] = 0
    return out


async def score_novel(novel_text: str, world_desc: str = "", persona_desc: str = "",
                      judge_provider: str | None = None) -> dict:
    """소설 텍스트를 4개 축으로 채점. 반환: {dim:1~5, comment, total}.

    judge_provider="openai" 등을 주면 채점관을 그 모델로 강제한다 — 선수(우리=Gemini)와
    다른 모델로 채점해 '심판 독립성'을 확보하기 위함. None이면 기존 체인.
    """
    if not (novel_text or "").strip():
        return _empty("빈 텍스트")

    prompt = f"[세계관]\n{world_desc}\n\n[작가 성향]\n{persona_desc}\n\n[소설]\n{novel_text}"
    try:
        raw = await llm.generate(
            EVAL_SYSTEM,
            [{"role": "user", "parts": [{"text": prompt}]}],
            json_mode=True,
            provider=judge_provider,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        out = {}
        for k in _DIMS:
            try:
                out[k] = max(0, min(5, int(data.get(k, 0) or 0)))
            except (ValueError, TypeError):
                out[k] = 0
        out["comment"] = str(data.get("comment", ""))[:120]
        out["total"] = sum(out[k] for k in _DIMS)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("소설 평가 실패: %s", e)
        return _empty()
