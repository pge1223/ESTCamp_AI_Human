"""작가 리액션 풀 (F-AS-05).

사용자(주인공)가 한 말/행동에 작가 캐릭터가 짧게 즉각 반응하는 말풍선 문장 모음.
감정(emotion) 버킷별로 작가 톤에 맞춰 미리 써둔다 → LLM이 입력의 감정만 분류하고,
실제 문장은 여기서 꺼낸다(작가 톤 100% 보장, 빠르고 저렴).

⚠️ 여기 문장 내용은 '콘텐츠'라 동완(F-CH-16 협업 멘트 세트)이 확장한다.
   윤정은 씨앗 몇 개만 넣어두고 API/꺼내는 로직을 담당.
"""
import random

# 감정 라벨 6종 (classify_emotion이 이 중 하나를 반환해야 함)
EMOTIONS = ["tension", "fear", "sadness", "joy", "calm", "resolve"]

# 작가별 × 감정별 리액션 풀 (씨앗 — 동완이 확장)
REACTIONS: dict[str, dict[str, list[str]]] = {
    "baekya": {  # 백야 — 호러, 짧고 단절적, 감정 직접서술 안 함, 여백
        "tension": ["그렇게 흘러가나요."],
        "fear":    ["뒤를 봐. 아니, 보지 마.", "그걸 느낀 게 너만은 아니야."],
        "sadness": ["어떤 건 묻어둬야 해.", "침묵이 더 무겁지."],
        "joy":     ["설명하지 않아도 충분합니다."],
        "calm":    ["너무 조용하군.", "이대로 둬도 될까."],
        "resolve": ["결국 택했군.", "돌이킬 순 없어."],
    },
    "charoun": {  # 차로운 — 추리, 관찰자 시점, 행동·사실 먼저, 복선
        "tension": ["그건 생각 못 했군요."],
        "fear":    ["그 떨림, 단서가 될 거야.", "두려움은 거짓말을 못 해."],
        "sadness": ["슬픔도 흔적을 남기지.", "숨기려는 게 보이는군."],
        "joy":     ["이건, 계산된 한수처럼 보이는군요"],
        "calm":    ["너무 평온한 게 수상한데.", "관찰하기 딱 좋군."],
        "resolve": ["좋은 선택이야. 근거는?", "그 결심, 기억해두지."],
    },
    "hanyeoreum": {  # 한여름 — 로맨스, 신체반응·감각 묘사, 여운
        "tension": ["흥미로운데요?"],
        "fear":    ["손 떨려도 괜찮아.", "무서우면 이쪽을 봐."],
        "sadness": ["…울어도 돼.", "그 마음, 알 것 같아."],
        "joy":     ["정말 좋은 표현인데요?"],
        "calm":    ["이 순간, 오래 두고 싶다.", "따뜻하네."],
        "resolve": ["네 마음이 정해졌구나.", "그 용기, 예쁘다."],
    },
    "kimdohyeon": {  # 김도현 — 일상, 낮은 시선, 작은 디테일, 담담함
        "tension": ["조금 의외인데요?"],
        "fear":    ["괜찮아, 천천히.", "겁나면 잠깐 쉬자."],
        "sadness": ["그런 날도 있지.", "말 안 해도 돼."],
        "joy":     ["이런 순간이 좋아요."],
        "calm":    ["이런 거 좋다, 그냥.", "평범한 게 제일이지."],
        "resolve": ["오, 해보려고?", "그래, 한번 가보자."],
    },
}

_DEFAULT_AUTHOR = "baekya"
_DEFAULT_EMOTION = "calm"


def pick_reaction(character_id: str, emotion: str, exclude: str | None = None) -> str:
    """작가·감정에 맞는 리액션 하나를 고른다. exclude(직전 리액션)는 피해서 반복을 줄인다."""
    by_author = REACTIONS.get(character_id) or REACTIONS[_DEFAULT_AUTHOR]
    pool = by_author.get(emotion) or by_author.get(_DEFAULT_EMOTION) or []
    if not pool:
        return ""
    choices = [r for r in pool if r != exclude] or pool
    return random.choice(choices)
