from __future__ import annotations

import json
import re

# story.py 에서 re-export — 기존 import 경로 호환 유지
from app.prompts.story import (  # noqa: F401
    CRITICAL_OUTPUT_RULE,
    INPUT_RULES,
    OUTPUT_RULES,
    PROGRESS_RULE,
    PROGRESS_RULE_ROMANCE,
    REACTION_PRIORITY_RULE,
    WRITER_STYLE_RULE,
    CONSISTENCY_SYSTEM,
    PACING_RULE,
    SCENE_CONTEXT_RULE,
    STORY_PROGRESS_RULE,
)


SUGGEST_NEXT_SYSTEM = """\
[창작 유도 어시스턴트]
사용자는 1인칭 주인공으로 이야기에 참여 중이다.
[세계관]·[등장인물]·[최근 대화]를 보고 사용자가 다음에 할 수 있는 선택지 3개를 제안한다.

[규칙]
- 제안은 반드시 사용자(주인공) 시점의 행동 또는 대사여야 함 (작가가 대신 쓰는 게 아니라 유도)
- 3개는 서로 다른 방향 (예: 도전적 / 조심스러운 / 감정적)
- 세계관·등장인물 설정에 어긋나지 않음
- 한 문장, 간결하게
- 형식: 큰따옴표면 대사, 일반 문장이면 행동

반드시 valid JSON만 출력:
{"suggestions": ["...", "...", "..."]}
"""

STUCK_HELP_SYSTEM = """\
[창작 막힘 도우미]
사용자가 다음 장면을 어떻게 전개할지 막혀 있다.
[세계관]·[등장인물]·[최근 대화]를 보고 이야기를 풀어갈 힌트를 준다.

[규칙]
- 정답을 주지 않음. 사용자가 스스로 선택할 수 있게 방향만 제시
- 현재 장면의 긴장감·감정선·미해결 요소를 짚어줌
- 힌트는 3개, 서로 다른 각도 (인물 / 사건 / 감정)
- 따뜻하고 격려하는 톤
- 한 문장씩, 간결하게

반드시 valid JSON만 출력:
{
  "situation": "지금 이야기의 상태 한 줄 요약",
  "hints": ["...", "...", "..."]
}
"""

def parse_ai_response(raw: str) -> dict:
    _default_state = {"trust_delta": 0, "event": None}
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        # JSON null → None 이 그대로 넘어오면 이후 슬라이싱에서 터지므로 "" 로 강제
        return {
            "narration":             data.get("narration") or "",
            "speaker":               data.get("speaker") or "",
            "dialogue":              data.get("dialogue") or "",
            "state_changes":         data.get("state_changes") or _default_state,
            "internal_note":         data.get("internal_note") or "",
            "out_of_genre":          bool(data.get("out_of_genre")),
            "genre_note":            data.get("genre_note") or "",
        }
    except (json.JSONDecodeError, AttributeError):
        pass

    # 폴백: 깨진 JSON(값에 따옴표 누락 등)에서 narration/dialogue를 정규식으로 추출
    def _grab(field: str) -> str:
        m = re.search(
            rf'"{field}"\s*:\s*"?(.*?)"?\s*'
            rf'(?=,\s*\n?\s*"(?:narration|dialogue|state_changes|internal_note)"|\n?\s*\}})',
            cleaned, re.DOTALL,
        )
        return m.group(1).strip().strip('"').rstrip(",").strip() if m else ""

    narration, dialogue, speaker = _grab("narration"), _grab("dialogue"), _grab("speaker")
    if narration or dialogue:
        return {
            "narration":     narration,
            "speaker":       speaker,
            "dialogue":      dialogue,
            "state_changes": _default_state,
            "internal_note": "",
        }
    # 최후: 원문 전체를 narration으로
    return {
        "narration":     raw,
        "speaker":       "",
        "dialogue":      "",
        "state_changes": _default_state,
        "story_phase":   "",
        "internal_note": "",
    }

MULTI_NPC_SYSTEM = """\
[조연 다중 반응]
아래 장면에서 등장한 조연들이 각자의 성격대로 동시에 반응한다.

[규칙]
- 각 조연은 자신의 성격·말투·관계에 맞게만 반응함
- 다른 조연의 반응을 따라 하거나 비슷하게 쓰지 않음
- 반응이 자연스럽게 이어지도록 순서 고려 (먼저 반응할 것 같은 인물 먼저)
- narration은 전체 장면 묘사, 각 조연 반응은 responses 배열에 분리
- 대사 없는 조연은 dialogue를 빈 문자열로 둠
- 반드시 한국어로만 작성

반드시 valid JSON만 출력:
{
  "narration": "전체 장면 묘사 (등장인물들의 행동·분위기)",
  "responses": [
    {
      "character_name": "조연 이름",
      "action": "이 조연의 행동·표정·반응 (짧게)",
      "dialogue": "이 조연의 대사 (없으면 빈 문자열)"
    }
  ],
  "state_changes": {
    "trust_delta": 0,
    "event": null
  }
}
"""

def build_multi_npc_prompt(
    world_context: str,
    npcs: list[dict],
    recent_dialogue: str,
) -> str:
    """
    F-CH-09 조연 다중 반응 프롬프트 조합.

    Args:
        world_context: 세계관 요약
        npcs: [{"name": "이름", "personality": "성격", "relationship": "관계"}, ...]
        recent_dialogue: 직전 대화 상황 (사용자 마지막 입력 포함)

    Returns:
        완성된 시스템 프롬프트
    """
    npc_block = "\n".join(
        f"- {npc['name']}: {npc.get('personality', '')} / 관계: {npc.get('relationship', '')}"
        for npc in npcs
    )

    return (
        f"{MULTI_NPC_SYSTEM}\n\n"
        f"[세계관]\n{world_context}\n\n"
        f"[등장 조연]\n{npc_block}\n\n"
        f"[현재 장면]\n{recent_dialogue}"
    )

# chats.py 호환용 alias
ASSISTANT_SUGGEST_SYSTEM = SUGGEST_NEXT_SYSTEM


# ── Voice Mirroring (F-VM) ─────────────────────────────────

VOICE_PROFILE_SYSTEM = """\
당신은 사용자가 제공한 문장 샘플에서 말투 특징만 추출하는 Voice Profile Analyzer입니다.

목표:
사용자 원문을 재작성하거나 흉내 내지 않습니다.
사용자 문장을 그대로 복사하지 않습니다.
사용자 말투의 반복 가능한 특징만 JSON으로 정리합니다.

분석 원칙:
1. 원문 문장 저장 금지
2. 원문 문장 재사용 금지
3. 개인정보, 실명, 연락처, 주소, 학교명, 회사명 저장 금지
4. 말투 특징만 추출
5. 샘플이 부족하면 확정하지 말고 추정 불가로 표시
6. 사용자가 특정 상황에서만 쓰는 표현은 일반 말투로 확정하지 않음
7. 욕설, 과한 유행어, 특정 밈은 사용 빈도가 높을 때만 특징으로 기록
8. 사용자의 말투를 과장하거나 희화화하지 않음
9. 문체 특징과 감정 반응 습관을 분리해서 분석
10. JSON 외의 설명 문장 출력 금지

판단 기준:
- confidence는 0.0에서 1.0 사이 숫자
- 샘플 3개 미만이면 confidence를 0.6 이하로 제한
- 특정 표현이 1회만 등장하면 common 항목에 넣지 않음
- 원문에 없는 말투를 추측해서 추가하지 않음

반드시 valid JSON만 출력:
{
  "speech_level": {"value": "반말 | 존댓말 | 섞임 | 추정 불가", "confidence": 0.0},
  "sentence_length": {"value": "짧음 | 보통 | 김 | 섞임 | 추정 불가", "confidence": 0.0},
  "rhythm": {"value": "단문 위주 | 장문 위주 | 끊어 말함 | 이어 말함 | 섞임 | 추정 불가", "notes": ""},
  "tone": {"primary": [], "secondary": [], "avoid_overdoing": []},
  "emotion_expression": {"value": "감정 직접 표현 | 농담으로 숨김 | 돌려 말함 | 과장해서 표현 | 거의 드러내지 않음 | 추정 불가", "notes": ""},
  "situation_styles": {
    "hesitation": "",
    "embarrassment": "",
    "affection": "",
    "refusal": "",
    "apology": "",
    "conflict": ""
  },
  "language_habits": {
    "common_endings": [],
    "common_fillers": [],
    "preferred_words": [],
    "rare_or_avoid_words": []
  },
  "punctuation_style": {
    "ellipsis": "없음 | 적음 | 보통 | 많음 | 추정 불가",
    "exclamation": "없음 | 적음 | 보통 | 많음 | 추정 불가",
    "question_mark": "없음 | 적음 | 보통 | 많음 | 추정 불가"
  },
  "emoji_style": {"value": "사용 안 함 | 가끔 사용 | 자주 사용 | 추정 불가", "examples_allowed": []},
  "slang_level": {"value": "없음 | 낮음 | 보통 | 높음 | 추정 불가", "notes": ""},
  "formality_shift": {"value": "친한 상대에게만 반말 | 대부분 반말 | 대부분 존댓말 | 상황 따라 섞임 | 추정 불가", "notes": ""},
  "response_density": {"value": "짧게 답함 | 한두 문장 설명함 | 감정 설명을 덧붙임 | 길게 풀어 말함 | 추정 불가", "notes": ""},
  "mirroring_risk": {"level": "낮음 | 보통 | 높음", "reason": ""},
  "generation_guidelines": [
    "사용자 원문 문장 그대로 복사하지 않음",
    "사용자 샘플의 고유 사건, 장소, 인물명 재사용하지 않음",
    "말투 특징만 반영함",
    "말투를 과장해 캐릭터처럼 만들지 않음",
    "상황 감정에 맞지 않는 이모지나 농담 추가하지 않음"
  ],
  "summary_for_user": "사용자에게 보여줄 수 있는 말투 요약 문장",
  "summary_for_prompt": "생성 프롬프트에 넣을 짧은 말투 요약"
}
"""

