"""
scripts/evidence_report.py
---------------------------
F-EV-06 차별점 근거 리포트 — "맨손 작성 vs 우리 서비스" 정량 비교.

강화된 점:
- BASELINE_SYSTEM 현실적으로 강화 (ChatGPT 잘 쓰는 사람 수준)
- 3회 평균으로 신뢰도 향상
- style_weakness 필드 출력 추가
- 결과를 JSON으로도 저장 (발표 자료용)

실행: backend 폴더에서
    python -m scripts.evidence_report
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio
import json
import os
from datetime import datetime

from app.core.config import settings
from app.services import llm, evaluate
from app.services.llm_router import LLMRouter

# ── 비교 엔진 결정 (강사님: "한쪽 GPT / 한쪽 우리") ─────────────────
# 베이스라인='맨손', 채점관='독립 심판'을 우리(Gemini)와 다른 계열 모델로 강제해 공정성 확보.
#   자동 선택: openai(GPT) → groq(Llama) 순으로 '살아있는' 첫 독립 모델(둘 다 Gemini와 다름).
#   - EVAL_GPT=0 으로 비교 비활성(전부 Gemini)
#   - EVAL_BASELINE_PROVIDER / EVAL_JUDGE_PROVIDER 로 수동 강제 가능(openai|groq|gemini)
_AUTO_ORDER = ["openai", "groq"]  # GPT 우선, 없거나 죽으면 Groq


def _has(provider: str) -> bool:
    if provider == "openai":
        return bool((settings.OPENAI_API_KEY or "").strip() or (settings.OPENAI_API_KEYS or "").strip())
    if provider == "groq":
        return bool((settings.GROQ_API_KEY or "").strip() or (settings.GROQ_API_KEYS or "").strip())
    return True  # gemini(우리 엔진)


_DISABLED = os.getenv("EVAL_GPT", "1") == "0"
_BASE_ENV = os.getenv("EVAL_BASELINE_PROVIDER")
_JUDGE_ENV = os.getenv("EVAL_JUDGE_PROVIDER")
# 실제 값은 main()의 사전점검(_pick) 후 확정 — 죽은 모델을 자동 회피하기 위함.
BASELINE_PROVIDER = None
JUDGE_PROVIDER = None

# ── 테스트 시나리오 ────────────────────────────────────────────
# 여러 시나리오로 돌릴수록 신뢰도 올라감

SCENARIOS = [
    {
        "name": "잠입수사_카페",
        "world_desc": "제목: 잠입 수사 / 장르: 추리 / 배경: 비 오는 밤의 카페. 알바생 민준은 사실 정체를 숨긴 잠입 형사다.",
        "persona_id": "charoun",
        "persona_desc": "차로운(추리): 관찰자 시점. 감정보다 행동과 사실을 먼저 쓴다. 복선을 자연스럽게 심는다.",
        "dialogue": [
            {"role": "user", "content": "나는 비에 젖은 채 카페 문을 열고 들어선다."},
            {"role": "ai",   "content": "민준이 무뚝뚝하게 고개를 들어 나를 본다. \"어서 오세요.\""},
            {"role": "user", "content": "나는 그의 눈빛에서 뭔가 다른 것을 느끼고 자리에 앉는다."},
        ],
    },
    {
        "name": "폐건물_공포",
        "world_desc": "장르: 호러 / 배경: 2019년 서울 외곽 폐건물. 주인공은 실종된 친구를 찾아 혼자 들어간다.",
        "persona_id": "baekya",
        "persona_desc": "백야(호러): 문장은 짧고 단절적. 감정을 직접 쓰지 않고 장면과 행동만 쓴다. 여백과 침묵을 표현한다.",
        "dialogue": [
            {"role": "user", "content": "나는 손전등을 켜고 계단을 올라간다."},
            {"role": "ai",   "content": "3층에서 문이 하나 열려 있었다. 어제는 잠겨 있었다."},
            {"role": "user", "content": "나는 그 안을 들여다본다."},
        ],
    },
    {
        "name": "재회_로맨스",
        "world_desc": "장르: 로맨스 / 배경: 현대 서울. 5년 만에 우연히 마주친 첫사랑.",
        "persona_id": "hanyeoreum",
        "persona_desc": "한여름(로맨스): 인물의 신체 반응을 먼저 쓴다. 감각적 묘사로 분위기를 깔고 감정을 올린다.",
        "dialogue": [
            {"role": "user", "content": "나는 지하철에서 그 사람을 발견한다."},
            {"role": "ai",   "content": "그가 먼저 나를 봤다. 5년 전과 같은 눈이었다."},
            {"role": "user", "content": "나는 뭐라고 해야 할지 모른 채 그 앞에 서 있다."},
        ],
    },
]

# ── 맨손 베이스라인 프롬프트 ───────────────────────────────────
# 현실적으로 강화 — "소설 좀 써봤다"는 사람이 ChatGPT에 쓸 법한 수준

BASELINE_SYSTEM = """\
당신은 한국 소설을 잘 쓰는 AI입니다.
주어진 [세계관]과 [작가 문체]를 최대한 살려, 아래 [대화]를 소설 한 장면으로 변환하세요.

조건:
- 한국어로만 작성
- 제시된 세계관 설정(인물·장소·관계)을 정확히 반영
- 제시된 작가 문체/성향을 살릴 것
- 지문과 대사를 자연스럽게 섞어, 인물의 감정과 분위기가 느껴지도록
- 300자 내외로
"""

BAR = "=" * 60


def _block(dialogue: list[dict]) -> str:
    return "\n".join(
        f"{'사용자' if m['role'] == 'user' else '상대'}: {m['content']}"
        for m in dialogue
    )


async def run_scenario(router: LLMRouter, scenario: dict, repeat: int = 3) -> dict:
    """단일 시나리오를 repeat회 돌려서 평균 점수 반환."""
    name = scenario["name"]
    world_desc = scenario["world_desc"]
    persona_id = scenario["persona_id"]
    persona_desc = scenario["persona_desc"]
    dialogue = scenario["dialogue"]

    base_scores, ours_scores = [], []

    # 공정 ablation: 맨손에도 세계관+페르소나를 똑같이 준다(='맥락 잘 준 사용자').
    # 우리와의 유일한 차이는 RAG(장기기억) 검색뿐 → 차이 = 순수 RAG 기여.
    baseline_user = f"[세계관]\n{world_desc}\n\n[작가 문체]\n{persona_desc}\n\n[대화]\n{_block(dialogue)}"

    for i in range(repeat):
        # 맨손 — 맥락 포함(세계관·페르소나). RAG만 빠짐. provider 지정 시 진짜 GPT/Llama.
        baseline = await llm.generate(
            BASELINE_SYSTEM,
            [{"role": "user", "parts": [{"text": baseline_user}]}],
            provider=BASELINE_PROVIDER,
        )
        # 우리
        ours = await router.generate_novel(dialogue, world_desc, persona_id=persona_id)

        # 채점관 — 선수와 다른 독립 모델로(있으면)
        s_base = await evaluate.score_novel(baseline, world_desc, persona_desc, judge_provider=JUDGE_PROVIDER)
        s_ours = await evaluate.score_novel(ours, world_desc, persona_desc, judge_provider=JUDGE_PROVIDER)

        base_scores.append(s_base)
        ours_scores.append(s_ours)

    # 평균 계산
    def avg(scores: list[dict]) -> dict:
        result = {}
        for k in evaluate._DIMS:
            result[k] = round(sum(s[k] for s in scores) / len(scores), 2)
        result["total"] = round(sum(result[k] for k in evaluate._DIMS), 2)
        result["comment"] = scores[-1].get("comment", "")
        result["style_weakness"] = scores[-1].get("style_weakness", "")
        return result

    return {
        "name": name,
        "baseline": avg(base_scores),
        "ours": avg(ours_scores),
        "repeat": repeat,
    }


def print_result(result: dict):
    name = result["name"]
    s_base = result["baseline"]
    s_ours = result["ours"]

    print(f"\n{BAR}")
    print(f" 시나리오: {name} ({result['repeat']}회 평균)")
    print(BAR)
    print(f"{'평가 항목':<20}{'맨손':>6}{'우리':>6}{'차이':>6}")
    print("-" * 60)
    for k in evaluate._DIMS:
        diff = s_ours[k] - s_base[k]
        sign = "+" if diff > 0 else ""
        print(f"{evaluate._DIM_LABEL[k]:<18}{s_base[k]:>6}{s_ours[k]:>6}{sign}{diff:>5.1f}")
    print("-" * 60)

    total_diff = s_ours["total"] - s_base["total"]
    sign = "+" if total_diff > 0 else ""
    print(f"{'합계 (20점 만점)':<18}{s_base['total']:>6}{s_ours['total']:>6}{sign}{total_diff:>5.1f}")
    print(BAR)
    print(f"맨손 총평: {s_base['comment']}")
    print(f"우리 총평: {s_ours['comment']}")
    if s_ours.get("style_weakness"):
        print(f"문체 개선점: {s_ours['style_weakness']}")

    verdict = (
        "✅ 우리 서비스 우위" if total_diff > 0
        else ("≈ 동률" if total_diff == 0 else "⚠️ 열위 — 점검 필요")
    )
    print(f"\n판정: {verdict} (격차 {sign}{total_diff:.1f}점)")


async def _preflight(provider: str) -> bool:
    """provider를 실제 1회 호출해 살아있는지 확인. 실패(크레딧 없음·인증 등) 시 사유 출력 후 False."""
    try:
        await llm.generate("ping", [{"role": "user", "parts": [{"text": "hi"}]}], provider=provider)
        return True
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "insufficient_quota" in msg or "quota" in msg or "429" in msg:
            why = "크레딧/잔액 없음 또는 쿼터 초과"
        elif "401" in msg or "invalid api key" in msg or "unauthorized" in msg:
            why = "키 인증 실패"
        else:
            why = f"{e.__class__.__name__}: {str(e)[:80]}"
        print(f" ⚠️  '{provider}' 사전점검 실패 → {why}")
        return False


async def _pick(explicit: str | None) -> str | None:
    """수동 지정이면 그것만 점검; 아니면 openai→groq 순으로 살아있는 첫 독립 모델 선택."""
    if explicit:
        return explicit if (explicit == "gemini" or await _preflight(explicit)) else None
    for p in _AUTO_ORDER:
        if _has(p) and await _preflight(p):
            return p
    return None


async def main():
    global BASELINE_PROVIDER, JUDGE_PROVIDER
    router = LLMRouter()
    all_results = []

    # 살아있는 독립 모델 자동 선택(죽은 모델은 크래시 대신 자동 회피)
    if not _DISABLED:
        BASELINE_PROVIDER = await _pick(_BASE_ENV)
        JUDGE_PROVIDER = (await _pick(_JUDGE_ENV)) if _JUDGE_ENV else BASELINE_PROVIDER

    ours_engine = "Vertex Gemini" if settings.USE_VERTEX else (settings.GEMINI_MODEL or "Gemini")

    def _label(provider: str | None) -> str:
        if provider == "openai":
            return settings.OPENAI_MODEL or "openai"
        if provider == "groq":
            return settings.GROQ_MODEL or "groq"
        return ours_engine

    base_engine = _label(BASELINE_PROVIDER)
    judge_engine = _label(JUDGE_PROVIDER)
    judge_independent = JUDGE_PROVIDER in ("openai", "groq")   # 심판이 우리(Gemini)와 다른 계열
    same_base = base_engine == ours_engine                      # 맨손=우리 베이스 모델 동일 → 순수 RAG ablation
    independent = base_engine != ours_engine                    # 맨손이 외부(타사) 모델

    print(BAR)
    print(" F-EV-06 차별점 근거 리포트 — 맨손 vs 우리 서비스")
    print(BAR)
    print(f" 베이스라인(맨손) 엔진 : {base_engine}")
    print(f" 우리 서비스    엔진 : {ours_engine} + RAG")
    print(f" 채점관(심판)   엔진 : {judge_engine}")
    if same_base:
        print(" ℹ️  맨손=우리와 같은 베이스 모델 + 동일 맥락(세계관·페르소나) → 차이 = 순수 RAG(장기기억) 기여 (공정 ablation).")
    if judge_independent:
        print(" ✅  채점관이 우리 엔진과 다른 계열 → 심판 독립성 확보.")
    else:
        print(" ⚠️  채점관이 우리 엔진과 같은 계열 → 심판 독립성 약함(자기채점 위험).")
    print(BAR)

    for scenario in SCENARIOS:
        result = await run_scenario(router, scenario, repeat=3)
        print_result(result)
        all_results.append(result)

    # 전체 평균
    print(f"\n{BAR}")
    print(" 전체 종합")
    print(BAR)
    for k in evaluate._DIMS:
        base_avg = round(sum(r["baseline"][k] for r in all_results) / len(all_results), 2)
        ours_avg = round(sum(r["ours"][k] for r in all_results) / len(all_results), 2)
        diff = ours_avg - base_avg
        sign = "+" if diff > 0 else ""
        print(f"{evaluate._DIM_LABEL[k]:<18}{base_avg:>6}{ours_avg:>6}{sign}{diff:>5.1f}")

    # JSON 저장 (발표 자료용) — 어떤 엔진으로 쟀는지 함께 기록(출처 추적)
    payload = {
        "engines": {"baseline": base_engine, "ours": f"{ours_engine}+RAG", "judge": judge_engine},
        "independent_comparison": independent,
        "results": all_results,
    }
    output_path = f"evidence_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n📄 결과 저장: {output_path}")
    print(BAR)


if __name__ == "__main__":
    asyncio.run(main())
