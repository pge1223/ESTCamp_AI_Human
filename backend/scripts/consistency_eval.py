"""설정 모순 탐지(F-QC-01) 정량 평가 — 출제 편향 제거판(독립 교차 라벨링).

차별점 평가표의 '설정 모순 탐지' 행을 정량화한다.

⚠️ 이전 버전의 결함: 테스트 케이스를 '내가' 출제하고 '내가' 라벨링 → 선택/확증 편향.
   이 판은 **독립 모델(Groq/Llama)이 같은 케이스를 따로 분류**하게 해 (저자 라벨 vs 독립 라벨)
   합의를 만든다. 둘이 갈리는 항목(=라벨이 애매하거나 저자 편향)을 드러내고,
   검수기(Gemini) 정확도를 ①저자 라벨 ②독립 라벨 ③합의셋(둘이 일치) 기준으로 각각 보고한다.
   합의셋 정확도가 가장 신뢰할 수 있는 수치다.

실행: backend 폴더에서
    python -m scripts.consistency_eval        (conda nodevelture, LLM 키 필요)
서버·DB 불필요. 독립 라벨러=EVAL_JUDGE_PROVIDER(기본 groq).
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import json
import asyncio

from app.core.config import settings
from app.services import consistency, llm


# ── 독립 라벨러: 검수기(Gemini)와 다른 모델이 같은 케이스를 따로 분류 ──
def _has_groq() -> bool:
    return bool((settings.GROQ_API_KEY or "").strip() or (settings.GROQ_API_KEYS or "").strip())


INDEP_PROVIDER = os.getenv("EVAL_JUDGE_PROVIDER") or ("groq" if _has_groq() else None)

INDEP_SYSTEM = (
    "너는 소설 설정 검수자다. [확립된 설정]을 기준으로 [문장]이 설정과 모순되는지 판정한다.\n"
    "설정과 충돌(직접/간접/추론상)하면 label='모순', 충돌 없으면 label='정상'.\n"
    '오직 JSON만: {"label": "모순"}  또는  {"label": "정상"}'
)


async def _indep_label(facts: str, text: str) -> str:
    """독립 모델의 분류('모순'/'정상'). 실패 시 '불명'."""
    if not INDEP_PROVIDER:
        return "불명"
    prompt = f"[확립된 설정]\n{facts}\n\n[문장]\n{text}"
    try:
        raw = await llm.generate(
            INDEP_SYSTEM, [{"role": "user", "parts": [{"text": prompt}]}],
            json_mode=True, provider=INDEP_PROVIDER,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        lab = str(json.loads(cleaned).get("label", "")).strip()
        return lab if lab in ("모순", "정상") else "불명"
    except Exception:
        return "불명"

# ── 라벨링된 평가 세트 (사람 정답) ────────────────────────────────
# tier: '명백'=직접 충돌 / '미묘'=시간선·인원수·관계·추론이 필요한 간접 모순
# 각 facts 아래: 모순 1 + (헷갈릴 수 있는) 정상 1 대조쌍
CASES = [
    # ── 명백 (직접 충돌) ──────────────────────────────────────
    {
        "tier": "명백",
        "facts": "민준은 잠입 수사 중인 형사다. 카페에서 알바생으로 위장 중이다.",
        "items": [
            {"text": "민준은 사실 병원에서 일하는 외과 의사였다.", "label": "모순"},
            {"text": "민준은 주문서를 받아들고 무뚝뚝하게 고개를 끄덕였다.", "label": "정상"},
        ],
    },
    {
        "tier": "명백",
        "facts": "유나는 3년 전 화재로 동생을 잃었고, 그 뒤로 불을 몹시 무서워한다.",
        "items": [
            {"text": "유나는 모닥불 앞에서 환하게 웃으며 맨손으로 불씨를 집어 들었다.", "label": "모순"},
            {"text": "유나는 촛불이 흔들리자 자기도 모르게 손을 움츠렸다.", "label": "정상"},
        ],
    },
    {
        "tier": "명백",
        "facts": "이 마을에는 전기가 들어오지 않는다. 사람들은 밤이면 호롱불을 켠다.",
        "items": [
            {"text": "그는 벽의 전등 스위치를 올려 형광등을 환하게 켰다.", "label": "모순"},
            {"text": "그는 호롱불 심지를 돋우어 어두운 방을 밝혔다.", "label": "정상"},
        ],
    },
    {
        "tier": "명백",
        "facts": "이 왕국에는 마법이 존재하지 않는다. 모든 일은 오직 인간의 힘으로 해결된다.",
        "items": [
            {"text": "마법사가 주문을 외우자 굳게 닫힌 성문이 저절로 활짝 열렸다.", "label": "모순"},
            {"text": "병사 여럿이 도르래에 매달려 무거운 성문을 힘겹게 끌어 올렸다.", "label": "정상"},
        ],
    },
    # ── 미묘 (간접·추론 필요) ─────────────────────────────────
    {
        "tier": "미묘",
        "facts": "수아는 오전 9시에 출근했고, 점심시간이 되어서야 김 부장을 처음 만났다.",
        "items": [
            # 첫 만남이 점심인데 출근 직후 9시에 이미 동행 → 시간선 모순
            {"text": "출근하자마자 9시, 수아는 김 부장과 나란히 엘리베이터에 올랐다.", "label": "모순"},
            {"text": "점심을 먹고 자리로 돌아온 수아는 그제야 김 부장의 이름을 외웠다.", "label": "정상"},
        ],
    },
    {
        "tier": "미묘",
        "facts": "그 집의 형제는 셋뿐이다. 첫째 도윤, 둘째 도현, 막내 도경.",
        "items": [
            # 넷째 등장 → 인원수 모순
            {"text": "넷째 도진이 형들 사이를 비집고 들어와 투정을 부렸다.", "label": "모순"},
            {"text": "막내 도경은 두 형의 눈치를 번갈아 살폈다.", "label": "정상"},
        ],
    },
    {
        "tier": "미묘",
        "facts": "노인은 두 눈을 잃어 앞을 전혀 보지 못한다. 평생 소리와 손끝으로 세상을 읽었다.",
        "items": [
            # 앞을 못 보는데 '색'을 알아봄 → 시각 능력 모순(간접)
            {"text": "노인은 멀리서 다가오는 손녀의 빨간 외투를 한눈에 알아보고 손을 흔들었다.", "label": "모순"},
            {"text": "노인은 익숙한 발소리만으로 손녀가 온 것을 알고 손을 흔들었다.", "label": "정상"},
        ],
    },
    {
        "tier": "미묘",
        "facts": "민호와 세진은 이혼한 지 5년 된 남남이다. 서로 연락도 끊고 지낸다.",
        "items": [
            # 이혼한 남남인데 '남편/아내'로 묘사 → 관계 모순(간접)
            {"text": "남편 민호는 아내 세진에게 아침상을 차려주며 다정하게 웃었다.", "label": "모순"},
            {"text": "민호는 길에서 세진을 마주치고도 모른 척 발걸음을 옮겼다.", "label": "정상"},
        ],
    },
    {
        "tier": "미묘",
        "facts": "이 도시는 해가 진 뒤 외출이 법으로 금지돼 있다. 밤거리는 늘 텅 비어 있다.",
        "items": [
            # 야간 외출 금지인데 한밤 광장이 북적 → 규칙 모순(추론)
            {"text": "한밤중, 광장은 산책 나온 시민들로 북적이며 웃음소리가 가득했다.", "label": "모순"},
            {"text": "해가 떨어지자 거리의 사람들이 서둘러 집 안으로 사라졌다.", "label": "정상"},
        ],
    },
    {
        "tier": "미묘",
        "facts": "지훈은 어릴 때 사고로 오른팔을 잃어, 의수를 쓰고 한 손으로 생활한다.",
        "items": [
            # 한 손인데 '두 손으로' → 신체 설정 모순(간접)
            {"text": "지훈은 두 손으로 무거운 상자를 번쩍 들어 가슴에 꼭 끌어안았다.", "label": "모순"},
            {"text": "지훈은 의수로 상자를 받치고 성한 손으로 균형을 잡으며 옮겼다.", "label": "정상"},
        ],
    },
    # ── 애매 (사람도 갈릴 수 있음 — 분쟁 surface 용) ─────────────
    {
        "tier": "애매",
        "facts": "지아는 엄격한 채식주의자로, 고기를 일절 입에 대지 않는다.",
        "items": [
            # 먹었다고 명시 안 함 — 권유에 젓가락만 들었을 수도. 애매.
            {"text": "회식 자리에서 동료가 고기를 권하자 지아는 마지못해 젓가락을 들었다.", "label": "정상"},
            # 직접 먹음 → 모순(이건 비교적 분명)
            {"text": "지아는 노릇하게 구워진 삼겹살을 입에 넣고 흡족하게 웃었다.", "label": "모순"},
        ],
    },
    {
        "tier": "애매",
        "facts": "세라는 목소리를 내지 못하는 농인이며, 평소 수화로 대화한다.",
        "items": [
            # '발표'가 수화 발표일 수도 → 애매
            {"text": "세라는 청중 앞에서 또박또박 발표를 이어 갔다.", "label": "정상"},
            # 마이크로 열창 → 모순(비교적 분명)
            {"text": "세라는 노래방에서 마이크를 잡고 큰 소리로 열창했다.", "label": "모순"},
        ],
    },
]

REPEATS = 2
BAR = "=" * 64


def _verdict(flagged: int, repeats: int) -> str:
    return "모순" if flagged >= (repeats + 1) // 2 else "정상"


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100*a/b:.0f}%)" if b else f"{a}/0 (-)"


async def main():
    n_items = sum(len(c["items"]) for c in CASES)
    print(BAR)
    print(" 설정 모순 탐지(F-QC-01) — 출제 편향 제거(독립 교차 라벨링)")
    print(f" {len(CASES)}세트 · 항목 {n_items} · 검수기=Vertex Gemini · 독립라벨러={INDEP_PROVIDER or '없음'}")
    print(BAR)

    rows = []  # (tier, text, my, indep, checker)
    for case in CASES:
        facts, tier = case["facts"], case["tier"]
        print(f"\n[{tier}] {facts}")
        for item in case["items"]:
            my = item["label"]
            indep = await _indep_label(facts, item["text"])
            flagged = 0
            for _ in range(REPEATS):
                r = await consistency.check(facts, item["text"])
                if not r["consistent"]:
                    flagged += 1
            ck = _verdict(flagged, REPEATS)
            rows.append((tier, item["text"], my, indep, ck))
            agree = "✅" if ck == my else "❌"
            disp = "" if my == indep else "  ⚠라벨분쟁"
            print(f"   나={my} 독립={indep} 검수기={ck} {agree}{disp}  ← {item['text'][:26]}")

    valid = [r for r in rows if r[3] in ("모순", "정상")]      # 독립 라벨 유효
    consensus = [r for r in valid if r[2] == r[3]]            # 나==독립(신뢰 ground-truth)
    disputed = [r for r in valid if r[2] != r[3]]

    lab_agree = len(consensus)
    ck_my = sum(1 for r in rows if r[4] == r[2])
    ck_indep = sum(1 for r in valid if r[4] == r[3])
    ck_cons = sum(1 for r in consensus if r[4] == r[2])
    cons_mosun = [r for r in consensus if r[2] == "모순"]
    cons_norm = [r for r in consensus if r[2] == "정상"]
    rec = sum(1 for r in cons_mosun if r[4] == "모순")
    spec = sum(1 for r in cons_norm if r[4] == "정상")

    print(f"\n{BAR}")
    print(" 종합 — 라벨 신뢰도 먼저, 그 다음 검수기 정확도")
    print(BAR)
    print(f"  라벨 합의(나↔독립)        : {_pct(lab_agree, len(valid))}  — 낮으면 내 라벨이 애매/편향")
    print(f"  검수기 정확도 vs 내 라벨   : {_pct(ck_my, len(rows))}")
    print(f"  검수기 정확도 vs 독립 라벨 : {_pct(ck_indep, len(valid))}")
    print(f"  ▶ 검수기 정확도 vs 합의셋  : {_pct(ck_cons, len(consensus))}  ← 가장 신뢰 (둘 다 동의한 것만)")
    print(f"      └ 합의셋 모순탐지(recall)     : {_pct(rec, len(cons_mosun))}")
    print(f"      └ 합의셋 정상통과(specificity): {_pct(spec, len(cons_norm))}")
    print(BAR)
    if disputed:
        print(f" ⚠️ 라벨 분쟁 {len(disputed)}건 (나≠독립) — 내 출제/라벨이 애매했던 항목:")
        for r in disputed:
            print(f"    [{r[0]}] 나={r[2]} vs 독립={r[3]}  ← {r[1][:40]}")
        print(BAR)


if __name__ == "__main__":
    asyncio.run(main())
