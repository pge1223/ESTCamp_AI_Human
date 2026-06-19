"""문체 RAG 시연 데모 — "문체 예시를 켰을 때 vs 껐을 때".

같은 대화를 같은 작가(한여름)로 소설화하되, 문체 RAG(few-shot)만 켜고/끄고 비교한다.
  - OFF: 페르소나 추상 규칙만 (build_novel_system)
  - ON : 거기에 장면과 가까운 문체 예시를 few-shot으로 주입
두 결과를 evaluate.py로 채점해 '작가 문체 뚜렷함' 점수 차이를 보여준다.

발표용. 실행: backend 폴더에서
    python -m scripts.style_demo   (conda nodevelture 환경, LLM 키 필요)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio

from app.services import style, evaluate
from app.services.llm_router import LLMRouter

PERSONA_ID = "hanyeoreum"
PERSONA_DESC = "한여름(로맨스): 신체 반응(심장·호흡·시선·손끝)을 먼저 쓰고 감각 묘사로 감정을 올린다. 여운을 남긴다."
WORLD_DESC = "제목: 비 오는 카페 / 장르: 로맨스 / 배경: 비 오는 밤의 조용한 카페."
DIALOGUE = [
    {"role": "user", "content": "나는 비에 젖은 채 카페 문을 열고 들어선다."},
    {"role": "assistant", "content": "그가 고개를 들어 나를 본다. 눈이 마주친다."},
    {"role": "user", "content": "나는 머뭇거리다 그의 맞은편에 앉는다."},
]

BAR = "=" * 62


def _block(d):
    return "\n".join(f"{'사용자' if m['role']=='user' else '상대'}: {m['content']}" for m in d)


def _box(title, text, score):
    print(f"\n┌─ {title} " + "─" * max(0, 48 - len(title)))
    body = (text or "").strip().replace("\n", "\n│ ")
    print("│ " + body[:240])
    print(f"│ ── 점수: 문체 {score['style_distinct']}/5 · 합계 {score['total']}/20  ({score['comment']})")
    print("└" + "─" * 54)


async def main():
    router = LLMRouter()
    print(BAR)
    print(" 문체 RAG 시연 — 한여름 작가, few-shot 껐을 때 vs 켰을 때")
    print(BAR)

    # 켰을 때 어떤 예시가 들어가는지 미리 보여줌
    used = await style.retrieve_examples(PERSONA_ID, _block(DIALOGUE), k=3)
    print("\n[ON일 때 주입되는 문체 예시 — 이 장면과 가까운 것]")
    for e in used:
        print("  •", e)

    # LLM 변동성을 줄이기 위해 양쪽을 N회 생성·채점해 평균낸다.
    N = 3

    async def avg_score(use_style):
        styles, totals, last = [], [], ""
        for _ in range(N):
            text = await router.generate_novel(DIALOGUE, WORLD_DESC, persona_id=PERSONA_ID, use_style=use_style)
            s = await evaluate.score_novel(text, WORLD_DESC, PERSONA_DESC)
            styles.append(s["style_distinct"])
            totals.append(s["total"])
            last = text
        return {
            "style_distinct": round(sum(styles) / N, 2),
            "total": round(sum(totals) / N, 2),
            "comment": f"{N}회 평균 (문체 {styles})",
        }, last

    print(f"\n각 조건 {N}회 생성·채점 평균 중...")
    s_off, off = await avg_score(False)
    s_on, on = await avg_score(True)

    _box("❌ 문체 RAG OFF (추상 규칙만)", off, s_off)
    _box("✅ 문체 RAG ON (예시 few-shot)", on, s_on)

    print("\n" + BAR)
    d_style = round(s_on["style_distinct"] - s_off["style_distinct"], 2)
    d_total = round(s_on["total"] - s_off["total"], 2)
    print(f"문체 뚜렷함 차이(평균): {d_style:+.2f}   ·   합계 차이(평균): {d_total:+.2f}")
    if d_style > 0 or d_total > 0:
        print("판정: ✅ 문체 RAG가 작가 문체를 더 살림")
    elif d_style == 0 and d_total == 0:
        print("판정: ≈ 차이 미미 — 추상 규칙이 이미 문체를 잘 잡음(엔진/샘플 개선 여지)")
    else:
        print("판정: ⚠️ OFF가 높음 — 추상 규칙만으로 충분하거나 엔진 변동. GPT·샘플 확대 권장")
    print(BAR)


if __name__ == "__main__":
    asyncio.run(main())
