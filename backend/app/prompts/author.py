"""작가 AI 채팅 전용 프롬프트"""
from app.core.personas import PERSONA_PROMPTS, _AUTHOR_PERSONALITY, load_persona_rule


def build_author_system(
    author_id: str,
    world_context: str = "",
    story_summary: str = "",
    memos: list = None,
    prev_questions: list = None,
    recent_story: list = None,
) -> str:
    """
    오른쪽 패널 작가 AI 채팅용 시스템 프롬프트.

    - 작가 페르소나 말투 유지
    - 세계관 + 현재 줄거리 + 메모를 알고 있음
    - 메타 레벨 대화: 플롯 조언, 복선 제안, 메모 관리, RAG 기반 사건 회상
    - 일반 텍스트로 응답 (JSON 불필요)
    """
    author = _AUTHOR_PERSONALITY.get(author_id)
    base   = PERSONA_PROMPTS.get(author_id, "")

    if not author:
        return "당신은 소설 창작을 돕는 작가 AI입니다. 한국어로 대화합니다."

    memos_section = ""
    if memos:
        memo_lines = "\n".join(
            f"- {m['text'] if isinstance(m, dict) else m}" for m in memos
        )
        memos_section = f"\n\n[작가 메모 (현재 등록된 항목)]\n{memo_lines}"

    story_section = f"\n\n[지금까지의 줄거리]\n{story_summary}" if story_summary else ""
    world_section = f"\n\n[세계관]\n{world_context}" if world_context else ""

    prev_section = ""
    if prev_questions:
        q_lines = "\n".join(f"- {q}" for q in prev_questions)
        prev_section = f"\n\n[이전 작가와 나눈 대화 맥락 — 사용자가 논의한 주요 질문들]\n{q_lines}"

    recent_story_section = ""
    if recent_story:
        lines = []
        for turn in recent_story:
            prefix = "사용자" if turn["role"] == "user" else "캐릭터"
            lines.append(f"{prefix}: {turn['content']}")
        recent_story_section = "\n\n[최근 스토리 대화 (최근 5턴)]\n" + "\n".join(lines)

    style_rules = load_persona_rule(author_id, compact=True)
    style_section = f"\n\n[스타일 규칙]\n{style_rules}" if style_rules else ""

    chat_shot = author.get("chat_shot", "")
    chat_shot_section = f"\n\n[채팅 예시 — 이 형식으로 답한다]\n{chat_shot}" if chat_shot else ""

    # [2026-06-17 START] 문장 추천 응답방식 — 모드 A/B 분리 (3버블 고정)
    response_mode_section = """\
[응답 방식 — 두 가지 모드]

▶ 모드 A — 문장 추천 요청
  트리거: 사용자가 '추천해줘', '문장 추천', '다음 문장', '이어서 써줘' 등을 말할 때
  출력: 지금 장면에 어울리는 소설 문장 1~2개를 바로 제시한다. 질문·설명 없이 문장만.

▶ 모드 B — 일반 조언
  트리거: 플롯·캐릭터·방향 등 메타 질문
  출력: 세계관·장르·분위기를 근거로 방향 조언. 소설 문장 직접 나열은 하지 않는다."""
    # [2026-06-17 END] 문장 추천 응답방식

    return f"""\
{base}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[작가 AI 채팅 모드]
지금은 소설 집필 파트너로서 사용자와 메타 레벨로 대화한다.
소설 속 장면을 직접 연기하는 것이 아니라, 작가의 시선으로 이야기를 함께 설계한다.

할 수 있는 것:
- 플롯 방향 조언, 복선 제안, 캐릭터 동기 분석
- 작가 메모 내용 확인 및 추가 제안 ("이걸 메모해두는 게 좋겠어" 식으로)
- 지금까지의 줄거리·사건을 바탕으로 다음 전개 추천
- 세계관 규칙과 충돌하는 아이디어를 짚어주기

{response_mode_section}

말투는 위의 작가 페르소나({author['name']}) 그대로 유지한다.
한국어로만 답한다.

[추천 마커 규칙]
응답 맨 마지막 줄에 반드시 아래 둘 중 하나를 단독으로 붙인다.
- 사용자에게 추가 정보·설명을 요청하는 경우: [SUGGEST:NO]
- 플롯 방향·다음 전개 등 실질적인 조언을 준 경우: [SUGGEST:YES]
마커 외에 다른 텍스트를 그 줄에 쓰지 않는다.
{world_section}{story_section}{memos_section}{recent_story_section}{prev_section}{style_section}{chat_shot_section}"""


def build_author_messages(
    author_id: str,
    world_context: str,
    story_summary: str,
    memos: list,
    author_history: list[dict],
    user_input: str,
    prev_questions: list = None,
    recent_story: list = None,
) -> list[dict]:
    """작가 AI 채팅용 messages 배열 구성."""
    system = build_author_system(
        author_id=author_id,
        world_context=world_context,
        story_summary=story_summary,
        memos=memos,
        prev_questions=prev_questions,
        recent_story=recent_story,
    )

    messages: list[dict] = [{"role": "system", "content": system}]

    # 최근 작가 채팅 히스토리 주입 (오래된 순)
    recent = list(reversed(author_history))[-10:]
    for h in recent:
        role = "user" if h["role"] == "user" else "assistant"
        messages.append({"role": role, "content": h["content"]})

    messages.append({"role": "user", "content": user_input})
    return messages
