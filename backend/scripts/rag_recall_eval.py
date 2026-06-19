"""기억 RAG 정량 평가 (엄밀판) — "묻어둔 설정을 '방해 정보들 속에서' 꺼내오는가".

이전 버전의 결함을 제거했다:
  (구) 방해 문장이 의미적으로 멀어(커피·비) 검색이 안 헷갈림 → '심은 걸 그대로 꺼냄'(동어반복).
  (신) target 비밀 + **의미적으로 비슷한 방해 비밀 3개**(다른 인물의 '숨겨진 정체')를 함께 심어,
       검색이 그 경쟁 속에서 옳은 것을 고르는지(recall@k·top-1)를 측정한다.

대조의 공정성:
  - 심기는 POST /messages 로만(생성 X) → DB Dialogue에 저장되어 검색 후보가 됨.
  - 스트리밍을 안 하므로 **rolling summary가 생성되지 않음** → OFF는 요약 누수 없이 깨끗.
  - target을 PROMPT_HISTORY_LIMIT(10)턴 밖으로 묻음 → OFF(최근창)는 target을 못 봄.
  - 따라서 ON−OFF 격차 = **순수 검색(retrieval)의 기여**.

지표:
  - 검색 recall@3 : 검색된 top-3에 target이 포함되는가
  - 검색 top-1    : 가장 유사한 1순위가 target인가(정밀도)
  - 방해 혼입     : 검색 결과에 방해 비밀이 섞이는가
  - 응답 일치 ON/OFF : 독립 LLM 심판(Groq/Llama) 판정

실행: backend 폴더에서  python -m scripts.rag_recall_eval   (conda nodevelture, DB·임베딩 키)
서버 불필요(인프로세스 TestClient). 응답심판=EVAL_JUDGE_PROVIDER(기본 groq).
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import asyncio
import json
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.user import User
from app.services import llm


# ── 독립 심판(응답 일치 판정) — 생성기(Gemini)와 다른 계열 ──────────
def _has_groq() -> bool:
    return bool((settings.GROQ_API_KEY or "").strip() or (settings.GROQ_API_KEYS or "").strip())


JUDGE_PROVIDER = os.getenv("EVAL_JUDGE_PROVIDER") or ("groq" if _has_groq() else None)

JUDGE_SYSTEM = (
    "너는 응답이 '주어진 비밀 사실'을 반영하는지 판정하는 엄격한 채점관이다.\n"
    "[비밀 사실]의 내용이 [응답]에 직접 언급되거나, 자연스럽게 암시·전제되면 reflects=true.\n"
    "전혀 드러나지 않거나(일반적 서술) 모순되면 reflects=false.\n"
    '오직 JSON만 출력: {"reflects": true}'
)


async def _judge(secret: str, response: str) -> bool:
    if not (response or "").strip() or not JUDGE_PROVIDER:
        return False
    prompt = f"[비밀 사실]\n{secret}\n\n[응답]\n{response}"
    try:
        raw = await llm.generate(
            JUDGE_SYSTEM, [{"role": "user", "parts": [{"text": prompt}]}],
            json_mode=True, provider=JUDGE_PROVIDER,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        return bool(json.loads(cleaned).get("reflects"))
    except Exception:
        return False


# ── 시나리오: target 1 + 의미적으로 비슷한 방해 비밀 3 ────────────────
# 방해들도 '특정 인물의 숨겨진 정체/사연' → 질문(target 인물)과 같은 의미 공간에서 경쟁
SCENARIOS = [
    {
        "name": "잠입형사",
        "target": {
            "secret": "민준은 사실 잠입 수사 중인 형사다. 정체를 숨기고 카페에서 일한다.",
            "keys": ["형사", "잠입", "수사"],
            "probe": "문득 궁금해진다. 민준의 진짜 정체가 뭐였지?",
        },
        "distractors": [
            {"secret": "세영은 사실 기억을 잃은 채 살아가고 있다.", "keys": ["기억", "잃"]},
            {"secret": "도훈은 빚쟁이를 피해 신분을 숨기고 도망 중이다.", "keys": ["빚", "도망"]},
            {"secret": "가은은 사실 그 회사 회장의 숨겨진 딸이다.", "keys": ["회장", "딸"]},
        ],
    },
    {
        "name": "화재트라우마",
        "target": {
            "secret": "유나는 3년 전 화재로 동생을 잃었고, 그 뒤로 불을 무서워한다.",
            "keys": ["화재", "동생", "불"],
            "probe": "유나는 왜 촛불 앞에서 그렇게 굳어버린 걸까?",
        },
        "distractors": [
            {"secret": "선우는 어린 시절 물에 빠져 죽을 뻔한 뒤로 바다를 피한다.", "keys": ["물", "바다"]},
            {"secret": "한별은 높은 곳에만 서면 다리가 풀리는 고소공포가 있다.", "keys": ["높", "고소"]},
            {"secret": "재인은 개에게 물린 뒤로 강아지만 보면 얼어붙는다.", "keys": ["개", "강아지"]},
        ],
    },
    {
        "name": "숨긴혈연",
        "target": {
            "secret": "태오는 사실 왕의 잃어버린 친아들, 즉 정통 후계자다.",
            "keys": ["왕", "아들", "후계"],
            "probe": "사람들이 태오의 출생을 두고 왜 그렇게 술렁였을까?",
        },
        "distractors": [
            {"secret": "리사는 적국에서 보낸 첩자로, 궁에 잠입해 있다.", "keys": ["첩자", "적국"]},
            {"secret": "무현은 사실 마지막 남은 용족의 후예다.", "keys": ["용족", "후예"]},
            {"secret": "연희는 죽은 줄 알았던 전 왕비가 변장한 모습이다.", "keys": ["왕비", "변장"]},
        ],
    },
    {
        "name": "이중생활",
        "target": {
            "secret": "지호는 낮에는 평범한 교사지만 밤에는 복면을 쓴 도둑이다.",
            "keys": ["도둑", "복면", "밤"],
            "probe": "지호가 밤마다 어디로 사라지는지, 그 비밀이 뭐였더라?",
        },
        "distractors": [
            {"secret": "민아는 사실 유명 작가인데 필명 뒤에 정체를 숨긴다.", "keys": ["작가", "필명"]},
            {"secret": "준서는 회사를 다니는 척하지만 실은 백수다.", "keys": ["백수", "회사"]},
            {"secret": "혜린은 밤마다 몰래 격투기 시합에 나간다.", "keys": ["격투", "시합"]},
        ],
    },
]

FILLERS = [
    "나는 따뜻한 커피를 한 모금 마신다.", "창밖에는 비가 내린다.",
    "나는 메뉴판을 천천히 살핀다.", "잔잔한 음악이 흐른다.",
    "나는 휴대폰으로 시간을 확인한다.", "옆 테이블에서 웃음소리가 난다.",
    "나는 의자를 고쳐 앉는다.", "문에 달린 종이 딸랑 울린다.",
    "나는 물을 한 잔 더 청한다.", "바깥이 점점 어두워진다.",
    "나는 가방에서 수첩을 꺼낸다.",
]  # target+방해(4) 뒤에 11개 → target이 최근 10턴 밖으로 확실히 밀려남

REPEATS = 3
BAR = "=" * 64


def _ask(c, sid, text, use_rag):
    out = {"narration": "", "dialogue": "", "memories": []}
    with c.stream("GET", f"/api/v1/chats/{sid}/stream", params={
        "content": text, "character_id": "hanyeoreum",
        "world_context": "", "mode": "author", "use_rag": str(use_rag).lower(),
    }) as resp:
        for line in resp.iter_lines():
            if line and line.startswith("data:"):
                try:
                    d = json.loads(line[5:].strip())
                    for key in out:
                        if key in d and d[key]:
                            out[key] = d[key]
                except Exception:
                    pass
    return out


def _kw(text: str, keys: list[str]) -> bool:
    return any(k in (text or "") for k in keys)


def _reply_text(ans: dict) -> str:
    return (ans["narration"] + " " + ans["dialogue"]).strip()


async def _make_user():
    suffix = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        u = User(username=f"recall_{suffix}", email=f"recall_{suffix}@t.com", hashed_password="x")
        s.add(u)
        await s.flush()
        uid = str(u.id)
        await s.commit()
    await engine.dispose()
    return uid


def _build_session(c, uid: str) -> str:
    w = c.post(f"/api/v1/worlds/?user_id={uid}", json={
        "title": "기억 평가", "description": "장기기억 테스트", "genre": "드라마",
        "setting": "", "rules": "",
    }).json()["id"]
    p = c.post(f"/api/v1/worlds/{w}/characters/", json={
        "user_id": uid, "name": "나", "role": "protagonist",
        "personality": "평범한 인물", "prompt": "", "is_ai_controlled": False,
    }).json()["id"]
    return c.post("/api/v1/sessions/", json={
        "world_id": w, "user_id": uid, "protagonist_id": p, "author_id": 3,
    }).json()["id"]


def collect_scenario(c, uid: str, sc: dict) -> dict:
    sid = _build_session(c, uid)
    tgt = sc["target"]
    distractors = sc["distractors"]

    def plant(text):   # 생성 없이 Dialogue에만 적재(검색 후보) — 싸고 깨끗
        c.post(f"/api/v1/chats/{sid}/messages", json={"content": text})

    plant(tgt["secret"])                 # target = 가장 오래된 턴
    for d in distractors:                # 의미적으로 비슷한 방해 비밀들
        plant(d["secret"])
    for f in FILLERS:                    # 최근창(10) 밖으로 target을 묻음
        plant(f)
    plant(tgt["probe"])                  # 질문 게시(최근)

    trials = []
    for _ in range(REPEATS):
        off = _ask(c, sid, tgt["probe"], use_rag=False)
        on = _ask(c, sid, tgt["probe"], use_rag=True)
        mems = on["memories"]
        trials.append({
            "recall": any(_kw(m, tgt["keys"]) for m in mems),
            "top1": bool(mems) and _kw(mems[0], tgt["keys"]),
            "confusion": any(_kw(m, d["keys"]) for m in mems for d in distractors),
            "on_text": _reply_text(on),
            "off_text": _reply_text(off),
        })
    return {"name": sc["name"], "secret": tgt["secret"], "trials": trials}


async def _judge_all(results: list[dict]):
    for r in results:
        for t in r["trials"]:
            t["hit_on"] = await _judge(r["secret"], t["on_text"])
            t["hit_off"] = await _judge(r["secret"], t["off_text"])


def main():
    uid = asyncio.run(_make_user())

    print(BAR)
    print(" 기억 RAG 정량(엄밀) — 방해 비밀 3개 속에서 target 검색")
    print(f" 시나리오 {len(SCENARIOS)}종 × (target1+방해3) × 잡담 {len(FILLERS)}턴 매장 × 각 {REPEATS}회")
    print(f" 생성기=Vertex Gemini / 응답심판={JUDGE_PROVIDER or '없음'}")
    print(BAR)

    results = []
    with TestClient(app) as c:
        for sc in SCENARIOS:
            results.append(collect_scenario(c, uid, sc))

    asyncio.run(_judge_all(results))

    for r in results:
        n = len(r["trials"])
        rec = sum(t["recall"] for t in r["trials"])
        t1 = sum(t["top1"] for t in r["trials"])
        conf = sum(t["confusion"] for t in r["trials"])
        hon = sum(t["hit_on"] for t in r["trials"])
        hoff = sum(t["hit_off"] for t in r["trials"])
        print(f"\n[{r['name']}]  (n={n})")
        print(f"  검색 recall@3 : {rec}/{n}   top-1 정답 : {t1}/{n}   방해 혼입 : {conf}/{n}")
        print(f"  응답 일치     : ON {hon}/{n}  vs  OFF {hoff}/{n}")

    tot = len(results) * REPEATS
    s_rec = sum(t["recall"] for r in results for t in r["trials"])
    s_t1 = sum(t["top1"] for r in results for t in r["trials"])
    s_conf = sum(t["confusion"] for r in results for t in r["trials"])
    s_on = sum(t["hit_on"] for r in results for t in r["trials"])
    s_off = sum(t["hit_off"] for r in results for t in r["trials"])

    print(f"\n{BAR}")
    print(" 종합")
    print(BAR)
    print(f"  검색 recall@3      : {s_rec}/{tot}  ({100*s_rec/tot:.0f}%)  — 방해 속에서 target 회수")
    print(f"  검색 top-1 정밀도   : {s_t1}/{tot}  ({100*s_t1/tot:.0f}%)  — 1순위가 target")
    print(f"  방해 혼입율         : {s_conf}/{tot}  ({100*s_conf/tot:.0f}%)  — 낮을수록 좋음")
    print(f"  응답 일치 ON        : {s_on}/{tot}  ({100*s_on/tot:.0f}%)")
    print(f"  응답 일치 OFF       : {s_off}/{tot}  ({100*s_off/tot:.0f}%)")
    gap = (s_on - s_off) / tot * 100
    print(f"  ▶ 응답 차별점(ON−OFF): {'+' if gap >= 0 else ''}{gap:.0f}%p")
    print(BAR)
    if s_off >= s_on:
        print(" ⚠️ OFF≥ON — 매장 부족/요약 누수. 점검 필요.")


if __name__ == "__main__":
    main()
