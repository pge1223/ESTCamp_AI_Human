"""
LLM-as-Judge: 페르소나 일관성 자동 평가
평가 기준: 목표 평균 4.0 / 5.0 이상
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import google.generativeai as genai

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

JUDGE_MODEL = "gemini-2.5-flash"

# 페르소나별 메타 정보 (평가 프롬프트용)
_PERSONA_META = {
    "baekya":     {"name": "백야(白夜)", "genre": "호러/미스터리", "philosophy": "공포는 보여주는 것이 아니라 안 보여주는 것이다"},
    "charoun":    {"name": "차로운",     "genre": "본격 추리",      "philosophy": "독자는 항상 작가보다 영리하다고 가정해라"},
    "hanyeoreum": {"name": "한여름",     "genre": "로맨스",         "philosophy": "심장이 두근거려야 페이지를 넘긴다"},
    "kimdohyeon": {"name": "김도현",     "genre": "일상/에세이",    "philosophy": "특별한 하루보다 평범한 순간이 더 문학적이다"},
}

_JUDGE_PROMPT = """\
당신은 소설 장르 전문 평가자입니다.
아래 텍스트가 지정된 작가 페르소나의 특성을 얼마나 잘 반영하는지 1~5점으로 평가하세요.

[작가 정보]
이름: {name} ({genre})
집필 철학: "{philosophy}"

[평가할 텍스트]
{text}

[평가 기준]
- 5점: 페르소나 문체·철학이 완벽하게 반영됨
- 4점: 대부분 일관성 있음, 사소한 이탈
- 3점: 평균적, 페르소나 특성 희미
- 2점: 일관성 부족, 다른 장르와 혼동
- 1점: 페르소나와 전혀 무관

[평가 시 체크 포인트]
- 문체가 해당 장르에 맞는가?
- 작가 철학이 글에 녹아있는가?
- 다른 페르소나와 혼동될 여지가 없는가?
- 가드레일(장르 이탈 방지)이 지켜졌는가?

[채점 예시 — 참고용]
텍스트: "빗소리가 유리창을 두드렸다. 먼저 눈을 피한 건 나였다."
페르소나: 백야(白夜) / 호러·미스터리
→ {{"score": 5, "reason": "짧은 문장, 감정 설명 없이 행동만 서술. 침묵의 미학 완벽 반영.", "strength": "공포를 암시만 하고 설명하지 않음", "weakness": "없음"}}

텍스트: "그날 밤 나는 정말 너무나도 무섭고 두려웠다."
페르소나: 백야(白夜) / 호러·미스터리
→ {{"score": 1, "reason": "감정을 직접 서술. 백야 철학('안 보여주는 것이 공포')과 정반대.", "strength": "없음", "weakness": "감정 설명 제거하고 신체 반응이나 장면으로 대체 필요"}}

JSON 형식으로만 응답하세요 (마크다운 없이):
{{"score": <1~5 정수>, "reason": "<구체적 이유 1~2문장>", "strength": "<잘된 점>", "weakness": "<개선점>"}}
"""


@dataclass
class JudgeResult:
    persona_id: str
    score: float          # 1~5
    reason: str
    strength: str = ""
    weakness: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def passed(self) -> bool:
        """목표 기준(4.0) 통과 여부."""
        return self.score >= 4.0


@dataclass
class BatchJudgeResult:
    results: list[JudgeResult]

    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(r.score for r in self.results) / len(self.results), 2)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(1 for r in self.results if r.passed) / len(self.results), 2)

    def summary(self) -> str:
        lines = [
            f"평균 점수: {self.average_score}/5.0",
            f"통과율: {self.pass_rate * 100:.0f}% (기준: 4.0점 이상)",
            "",
        ]
        for r in self.results:
            status = "✅" if r.passed else "❌"
            lines.append(f"{status} {r.persona_id}: {r.score}점 — {r.reason}")
        return "\n".join(lines)


async def judge_persona_consistency(
    persona_id: str,
    generated_text: str,
) -> JudgeResult:
    """
    단일 텍스트의 페르소나 일관성 평가.

    Args:
        persona_id: "baekya" | "charoun" | "hanyeoreum" | "kimdohyeon"
        generated_text: 평가할 AI 생성 텍스트

    Returns:
        JudgeResult (score 1~5, reason, strength, weakness)
    """
    meta = _PERSONA_META.get(persona_id)
    if not meta:
        raise ValueError(f"알 수 없는 페르소나: {persona_id}")

    prompt = _JUDGE_PROMPT.format(
        name=meta["name"],
        genre=meta["genre"],
        philosophy=meta["philosophy"],
        text=generated_text,
    )

    try:
        model = genai.GenerativeModel(JUDGE_MODEL)
        resp = await asyncio.to_thread(
            model.generate_content,
            [{"role": "user", "parts": [{"text": prompt}]}],
        )
        raw = resp.text.strip()

        # JSON 파싱 (마크다운 펜스 방어)
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw.strip())

        # score 범위 검증 (1~5 밖의 값 방어)
        score = max(1.0, min(5.0, float(data["score"])))

        return JudgeResult(
            persona_id=persona_id,
            score=score,
            reason=data.get("reason", ""),
            strength=data.get("strength", ""),
            weakness=data.get("weakness", ""),
        )

    except json.JSONDecodeError as e:
        logger.error("[judge] JSON 파싱 실패 — persona=%s: %s", persona_id, e)
        return JudgeResult(persona_id=persona_id, score=0.0, reason=f"파싱 오류: {e}")
    except Exception as e:
        logger.error("[judge] 평가 실패 — persona=%s: %s", persona_id, e)
        return JudgeResult(persona_id=persona_id, score=0.0, reason=f"평가 오류: {e}")


async def batch_judge(
    pairs: list[tuple[str, str]],
) -> BatchJudgeResult:
    """
    여러 (persona_id, text) 쌍을 병렬로 평가.

    Args:
        pairs: [("baekya", "텍스트1"), ("charoun", "텍스트2"), ...]

    Returns:
        BatchJudgeResult (평균 점수, 통과율, 개별 결과)
    """
    tasks = [judge_persona_consistency(pid, text) for pid, text in pairs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid: list[JudgeResult] = []
    for item in results:
        if isinstance(item, Exception):
            logger.error("[batch_judge] 오류: %s", item)
        else:
            valid.append(item)

    return BatchJudgeResult(results=valid)


# ── CLI 실행 (빠른 테스트용) ──────────────────────────────────

async def _run_test():
    """python -m model.evaluation.llm_judge 로 실행."""
    test_cases = [
        ("baekya",     "빗소리가 유리창을 두드렸다. 먼저 눈을 피한 건 나였다."),
        ("charoun",    "우연이라고 하기엔 타이밍이 너무 정확했다. 그는 내가 여기 온다는 걸 알고 있었다."),
        ("hanyeoreum", "따뜻한 조명 아래 그 사람이 있었다. 심장이 한 박자 늦게 뛰었다."),
        ("kimdohyeon", "고개를 들었더니 거기 있었다. 별일 아닌 것처럼."),
    ]

    print("=== LLM-as-Judge 평가 시작 ===\n")
    batch = await batch_judge(test_cases)
    print(batch.summary())

    print("\n=== 상세 결과 ===")
    for r in batch.results:
        print(f"\n[{r.persona_id}] {r.score}점")
        print(f"  이유: {r.reason}")
        print(f"  강점: {r.strength}")
        print(f"  개선: {r.weakness}")


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))
    asyncio.run(_run_test())
