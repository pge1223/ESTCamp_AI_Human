"""페르소나 정량 평가 — "같은 입력에 작가 4명이 다르게 쓰는가 / 서로 침범하는가".

강사님 지적("작가별 차이·페르소나 분리 테스트 결과가 없다 / 분류 모델 돌려봐라")에 대한 정량 근거.

지표(내용이 아닌 *문체*를 측정):
  1) LLM 블라인드 분류 정확도 — 생성물의 문체만 보고 4작가 중 누구인지 맞히기.
     높을수록 페르소나가 뚜렷이 구분됨(= 서로 침범 안 함). 강사님의 "분류 모델" 요구에 직접 대응.
  2) 문체 통계 — 문장 수·평균 문장 길이·신체반응어 빈도 (작가별 객관 수치 차이).
  3) 작가별 문체 점수 (evaluate.py, 1~5).
  ※ 임베딩 코사인은 같은 장면이면 내용이 지배해 문체 차이를 못 잡으므로 제외.

실행: backend 폴더에서  python -m scripts.persona_eval   (conda nodevelture, LLM 키 필요)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import re
import json
import asyncio

from app.services import llm, evaluate
from app.services.llm_router import LLMRouter

PERSONAS = [
    ("baekya",     "백야",   "짧고 단절적, 감정 직접서술 안 함, 여백·침묵"),
    ("charoun",    "차로운", "관찰자 시점, 행동·사실 먼저, 복선"),
    ("hanyeoreum", "한여름", "신체반응 먼저(심장·호흡·시선·손끝), 감각 묘사, 여운"),
    ("kimdohyeon", "김도현", "낮은 시선, 작은 디테일, 결론 안 냄, 호흡 섞기"),
]
NAME = {p[0]: p[1] for p in PERSONAS}
WORLD = "배경: 비 오는 밤의 조용한 카페."
DIALOGUE = [
    {"role": "user",      "content": "나는 비에 젖은 채 카페 문을 열고 들어선다."},
    {"role": "assistant", "content": "창밖으로 빗줄기가 거세게 쏟아진다."},
    {"role": "user",      "content": "나는 구석 자리에 앉아 누군가를 기다린다."},
]
RUNS = 2
BODY_WORDS = ["심장", "호흡", "시선", "손끝", "가슴", "숨", "맥박"]
BAR = "=" * 64

CLASSIFY_SYS = (
    "다음 글이 아래 4명 작가 중 누구의 문체인지 고른다. 내용(소재)이 아니라 "
    "문장 길이·리듬·묘사 방식 등 '문체'로만 판단한다.\n"
    "- 백야: 짧고 단절적, 감정 직접서술 안 함, 여백\n"
    "- 차로운: 관찰자 시점, 행동·사실 먼저, 복선\n"
    "- 한여름: 신체반응(심장·호흡·시선) 먼저, 감각 묘사, 여운\n"
    "- 김도현: 낮은 시선, 작은 디테일, 결론 안 냄\n"
    '반드시 JSON만: {"author": "백야|차로운|한여름|김도현"}'
)


def _stylometry(text):
    sents = [s for s in re.split(r"[.!?。\n]+", text) if s.strip()]
    n = len(sents) or 1
    avg_len = sum(len(s.strip()) for s in sents) / n
    body = sum(text.count(w) for w in BODY_WORDS)
    return len(sents), round(avg_len, 1), body


async def _classify(text):
    try:
        raw = await llm.generate(CLASSIFY_SYS, [{"role": "user", "parts": [{"text": text}]}], json_mode=True)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        return json.loads(cleaned).get("author", "")
    except Exception:
        return ""


async def main():
    router = LLMRouter()
    print(BAR); print(" 페르소나 정량 평가 — 같은 입력, 작가 4명"); print(BAR)
    print(f"\n[입력] {DIALOGUE[0]['content']} … (동일 입력을 4작가 × {RUNS}회 소설화)\n")

    texts = {}
    for pid, name, _ in PERSONAS:
        texts[pid] = [await router.generate_novel(DIALOGUE, WORLD, persona_id=pid) or "" for _ in range(RUNS)]
        print(f"[{name}] {texts[pid][0].strip()[:80]}…")

    # 1) 블라인드 분류 정확도
    print(f"\n{BAR}\n 1) LLM 블라인드 분류 (문체만 보고 작가 맞히기)\n{BAR}")
    correct = total = 0
    for pid, name, _ in PERSONAS:
        for r in range(RUNS):
            pred = await _classify(texts[pid][r])
            ok = (pred == name)
            correct += ok; total += 1
            print(f"  실제 {name:>4} → 예측 {pred or '?':>4}  {'✅' if ok else '❌'}")
    acc = correct / total if total else 0

    # 2) 문체 통계
    print(f"\n{BAR}\n 2) 문체 통계 (작가별 객관 수치)\n{BAR}")
    print(f"{'작가':>6}{'문장수':>8}{'평균문장길이':>14}{'신체반응어':>12}")
    for pid, name, _ in PERSONAS:
        ns, al, bw = _stylometry(texts[pid][0])
        print(f"{name:>6}{ns:>8}{al:>14}{bw:>12}")

    # 3) 문체 점수
    print(f"\n{BAR}\n 3) 작가별 문체 점수 (evaluate, 1~5)\n{BAR}")
    sc = {}
    for pid, name, desc in PERSONAS:
        s = await evaluate.score_novel(texts[pid][0], WORLD, desc)
        sc[pid] = s["style_distinct"]
        print(f"{name:>6} : 문체 {s['style_distinct']}/5 · 총점 {s['total']}/20")

    # 종합
    print(f"\n{BAR}\n 종합\n{BAR}")
    print(f"문체 분류 정확도 : {correct}/{total} = {acc*100:.0f}%   (높을수록 페르소나 구분 = 침범 적음)")
    print(f"평균 문체 점수   : {sum(sc.values())/len(sc):.2f}/5")
    verdict = ("✅ 페르소나가 문체로 뚜렷이 구분됨(서로 침범 적음)" if acc >= 0.75
               else "🟡 부분 구분 — 일부 작가 문체 강화 필요" if acc >= 0.5
               else "⚠️ 구분 약함 — 프롬프트/샘플 강화 필요")
    print(f"\n판정: {verdict}")
    print(BAR)


if __name__ == "__main__":
    asyncio.run(main())
