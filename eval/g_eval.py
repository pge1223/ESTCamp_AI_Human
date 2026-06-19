"""G-Eval 채점기 — 인터랙티브 소설 AI 응답 품질 평가.

judge 모델은 NodeVelture 백엔드(Gemini/Groq)와 **다른** 모델을 사용한다.
기본값: claude-opus-4-8 (ANTHROPIC_API_KEY 환경변수 필요)
"""
import json
import os
import re

from anthropic import Anthropic

_judge = None

def _get_judge() -> Anthropic:
    global _judge
    if _judge is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 없습니다.")
        _judge = Anthropic(api_key=api_key)
    return _judge


JUDGE_PROMPT = """\
당신은 인터랙티브 소설 AI의 응답을 평가하는 전문 편집자입니다.
아래 기준으로 각 항목에 1~5점을 채점하세요.

[채점 기준]
- persona_consistency : 작가·캐릭터 설정과 문체를 일관되게 유지하는가
- immersion           : 소설 문체, 장면 묘사, 분위기 조성이 뛰어난가
- naturalness         : 대화 흐름이 자연스럽고 어색하지 않은가
- anti_mirroring      : 사용자 입력을 그대로 반복하지 않고 새로운 전개를 만드는가

[채점 규칙]
1=매우 나쁨 / 2=나쁨 / 3=보통 / 4=좋음 / 5=매우 좋음
근거를 한 문장으로 먼저 쓴 뒤 점수를 준다.
anti_mirroring: 사용자 입력의 어절·구문이 그대로 나오면 1~2점, 완전히 다른 전개면 4~5점.

[세계관/캐릭터 설정]
{world_context}

[이번 대화]
사용자 입력: {user_input}

AI 나레이션: {narration}
AI 대사 ({speaker}): {dialogue}

반드시 JSON으로만 출력 (마크다운·설명 금지):
{{"reason": "...", "persona_consistency": n, "immersion": n, "naturalness": n, "anti_mirroring": n}}"""

JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "claude-opus-4-8")


def score(
    world_context: str,
    user_input: str,
    narration: str,
    dialogue: str,
    speaker: str = "",
) -> dict:
    """응답 하나를 채점해 dict 반환. 실패 시 {"error": ...} 반환."""
    prompt = JUDGE_PROMPT.format(
        world_context=world_context.strip() or "별도 설정 없음",
        user_input=user_input,
        narration=narration or "(없음)",
        dialogue=dialogue or "(없음)",
        speaker=speaker or "AI",
    )

    try:
        resp = _get_judge().messages.create(
            model=JUDGE_MODEL,
            max_tokens=512,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
    except Exception as e:
        return {"error": f"judge API 실패: {e}"}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 블록만 추출 시도
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {"error": "JSON 파싱 실패", "raw": text}


def avg_score(result: dict) -> float:
    """채점 결과에서 4개 항목 평균 반환."""
    keys = ["persona_consistency", "immersion", "naturalness", "anti_mirroring"]
    vals = [result[k] for k in keys if isinstance(result.get(k), (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else 0.0
