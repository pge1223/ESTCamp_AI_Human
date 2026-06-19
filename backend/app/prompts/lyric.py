"""가사적용 AI 프롬프트"""

LYRIC_EXTRACT_SYSTEM = """\
[가사 감정 분석기]
사용자가 입력한 노래 제목 또는 노래 분위기 힌트를 분석한다.

규칙:
- 가사 원문을 절대 출력하지 않는다.
- 저작권 보호를 위해 특정 가사 구절을 인용하지 않는다.
- 오직 감정·주제·분위기·서사 구조·강도만 추출한다.
- 노래를 모르면 입력 텍스트의 느낌만으로 추론한다.

반드시 JSON만 출력:
{
  "emotion": "핵심 감정 한 단어 (예: 그리움, 설렘, 체념, 기다림)",
  "theme": "서사 주제 (예: 이별 후 재회, 비밀스러운 사랑, 엇갈린 감정)",
  "mood": "분위기 키워드 2~3개 콤마 구분 (예: 새벽, 비, 고독)",
  "intensity": 0.0~1.0,
  "narrative": "이 노래가 담고 있는 서사 구조 한 줄 (예: 떠난 사람을 혼자 기다리는 밤의 독백)"
}"""


def build_lyric_scene_system(
    mode: str,
    world_context: str,
    story_summary: str,
    recent_turns: list | None = None,
) -> str:
    mode_instruction = (
        "위 [최근 대화] 또는 [이야기 흐름]을 바탕으로, 해당 장면을 [감정 데이터]의 감정으로 재해석해 새로운 산문 장면(3~5문장)을 쓴다."
        if mode == "transform"
        else "위 [세계관]·[이야기 흐름]·[최근 대화]를 참고해, [감정 데이터]의 분위기와 어울리는 새로운 장면 하나를 추천한다(장소·상황·인물 반응 포함, 3~5문장)."
    )

    parts = ["[가사 감정 적용 작가]"]
    if world_context:
        parts.append(f"[세계관]\n{world_context}")
    if story_summary:
        parts.append(f"[이야기 흐름]\n{story_summary}")
    if recent_turns:
        lines = "\n".join(
            f"{'사용자' if t['role'] == 'user' else 'AI'}: {t['content']}"
            for t in recent_turns[-4:]  # 최근 4턴만
        )
        parts.append(f"[최근 대화]\n{lines}")

    parts.append(f"""
[임무]
아래 [감정 데이터]를 받아 소설 장면을 생성한다.
{mode_instruction}

[필수 포함 요소 — 모두 반드시 있어야 함]
1. 현재 상황에 맞는 사건 1개 (무언가가 실제로 일어나야 한다)
2. 등장인물 간 대화 3~10줄 (직접 대사, 큰따옴표 사용)
3. 감정 변화 포인트 1개 (장면 전후로 인물의 감정이 달라져야 한다)
4. 노래의 핵심 정서를 상징하는 구체적 행동 1개 (추상적 묘사 금지 — 실제 행동)
5. 이전 장면보다 이야기가 진전되어야 한다 (같은 상태로 끝나면 안 됨)

[금지]
- 분위기·감정만 묘사하고 아무 일도 일어나지 않는 장면
- 가사 원문·특정 노래 구절 인용
- "고독이 흘렀다", "감정이 물결쳤다" 같은 추상 서술로만 채우는 것
- JSON·마크다운·제목·설명 출력 — 장면 텍스트만
""")

    return "\n\n".join(parts)
