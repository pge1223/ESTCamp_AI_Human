"""개인화 RAG 인과 e2e — 저장 문장 톤이 '취향저격' 추천을 실제로 바꾸는가.

통제 실험: 동일한 세계관·장면·작가, **저장 문장만 다른** 3명.
  - DARK : 어둡고 단절적·짧은 문장 저장
  - WARM : 따뜻하고 서정적·긴 문장 저장
  - NONE : 저장 문장 없음(개인화 근거 없음 → 베이스라인)

각자 /author/taste-recommend 를 R회 호출 → 추천(narration+dialogue)을
**독립 심판(Groq/Llama)**이 톤 0~10(0=어두움/단절, 10=따뜻/서정)으로 블라인드 채점.

RAG가 작동하면: DARK 평균 < NONE < WARM 평균. (효과 = WARM−DARK)
※ 우리 측정 교훈상 '검색≠생성'이라 효과가 작게 나올 수 있다 — 그대로 보고한다.

실행: backend 폴더에서  python -m scripts.personalize_e2e
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import json
import uuid
import asyncio

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.saved_sentence import SavedSentence
from app.services import llm

AUTHOR_ID = "kimdohyeon"   # 모든 유저 동일(통제변인)
REPEATS = 3                # 유저당 endpoint 호출 횟수
SCENE = "그는 문을 열고 방 안으로 들어섰다."   # 중립 장면(동일)

DARK = [
    "비가 멈추지 않았다. 골목은 검게 젖었다.",
    "그는 말이 없었다. 어둠만이 답했다.",
    "문이 닫혔다. 끝이었다.",
    "차가운 손. 식은 커피. 텅 빈 방.",
    "아무도 오지 않았다.",
]
WARM = [
    "아침 햇살이 커튼 사이로 부드럽게 스며들어 방 안을 노랗게 물들였다.",
    "그녀는 환하게 웃으며, 오래 기다린 사람처럼 두 팔을 활짝 벌렸다.",
    "갓 구운 빵 냄새가 부엌 가득 퍼지고, 창밖에선 새들이 정답게 지저귀었다.",
    "따뜻한 차 한 잔을 사이에 두고 두 사람은 도란도란 이야기를 나누었다.",
    "봄바람이 꽃잎을 실어와 그의 어깨에 살며시 내려앉았다.",
]

JUDGE_PROVIDER = "groq" if (settings.GROQ_API_KEY or settings.GROQ_API_KEYS) else None
JUDGE_SYSTEM = (
    "너는 문체 톤 평가자다. 주어진 [문장]의 톤을 0~10 정수로 채점한다.\n"
    "0 = 매우 어둡고 단절적이며 짧고 건조한 문체.\n"
    "10 = 매우 따뜻하고 서정적이며 부드럽고 긴 문체.\n"
    '오직 JSON만: {"score": 5}'
)
BAR = "=" * 64


async def _judge_tone(text: str) -> float | None:
    if not (text or "").strip() or not JUDGE_PROVIDER:
        return None
    try:
        raw = await llm.generate(
            JUDGE_SYSTEM, [{"role": "user", "parts": [{"text": f"[문장]\n{text}"}]}],
            json_mode=True, provider=JUDGE_PROVIDER,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        return float(json.loads(cleaned).get("score"))
    except Exception:
        return None


async def _setup_users():
    """3명 생성 + DARK/WARM 저장 문장 적재. uid 3개 반환."""
    uids = {}
    async with AsyncSessionLocal() as s:
        for name, saved in (("DARK", DARK), ("WARM", WARM), ("NONE", [])):
            suf = uuid.uuid4().hex[:8]
            u = User(username=f"pz{name}_{suf}", email=f"pz{name}_{suf}@t.com", hashed_password="x")
            s.add(u)
            await s.flush()
            uids[name] = str(u.id)
            for c in saved:
                s.add(SavedSentence(user_id=u.id, content=c))
        await s.commit()
    await engine.dispose()
    return uids


def _build_session(c, uid: str) -> str:
    w = c.post(f"/api/v1/worlds/?user_id={uid}", json={
        "title": "어느 날의 기록", "description": "한 사람의 하루", "genre": "드라마",
        "setting": "현대 도시의 작은 방", "rules": "",
    }).json()["id"]
    p = c.post(f"/api/v1/worlds/{w}/characters/", json={
        "user_id": uid, "name": "그", "role": "protagonist",
        "personality": "조용한 사람", "prompt": "", "is_ai_controlled": False,
    }).json()["id"]
    sid = c.post("/api/v1/sessions/", json={
        "world_id": w, "user_id": uid, "protagonist_id": p, "author_id": 4,
    }).json()["id"]
    c.post(f"/api/v1/chats/{sid}/messages", json={"content": SCENE})  # 동일 장면 적재
    return sid


def _recommend(c, sid: str, uid: str) -> list[str]:
    """taste-recommend 호출 → 추천 텍스트(narration+dialogue) 리스트."""
    r = c.post(f"/api/v1/chats/{sid}/author/taste-recommend",
               json={"user_id": uid, "author_id": AUTHOR_ID})
    if r.status_code != 200:
        return []
    out = []
    for item in r.json().get("recommendations", []):
        txt = (item.get("narration", "") + " " + item.get("dialogue", "")).strip()
        if txt:
            out.append(txt)
    return out


def main():
    uids = asyncio.run(_setup_users())
    print(BAR)
    print(" 개인화 RAG 인과 e2e — 저장 톤이 추천을 바꾸는가")
    print(f" 동일 세계관·장면·작가({AUTHOR_ID}) · 유저당 {REPEATS}회 · 심판={JUDGE_PROVIDER}")
    print(BAR)

    recs = {"DARK": [], "WARM": [], "NONE": []}
    with TestClient(app) as c:
        for name in ("DARK", "WARM", "NONE"):
            sid = _build_session(c, uids[name])
            for _ in range(REPEATS):
                recs[name].extend(_recommend(c, sid, uids[name]))

    # 톤 채점(독립 심판)
    async def _score_all():
        scored = {}
        for name, texts in recs.items():
            vals = []
            for t in texts:
                v = await _judge_tone(t)
                if v is not None:
                    vals.append((t, v))
            scored[name] = vals
        return scored

    scored = asyncio.run(_score_all())

    print()
    for name in ("DARK", "WARM", "NONE"):
        vals = scored[name]
        n = len(vals)
        avg = sum(v for _, v in vals) / n if n else 0
        print(f"[{name}] 추천 {n}개 · 평균 톤 {avg:.1f}/10  (0=어두움 … 10=따뜻)")
        for t, v in vals[:4]:
            print(f"   {v:>4.0f} | {t[:46]}")
        if n > 4:
            print(f"   … 외 {n-4}개")
        print()

    def _avg(name):
        vals = scored[name]
        return sum(v for _, v in vals) / len(vals) if vals else 0

    d, w, no = _avg("DARK"), _avg("WARM"), _avg("NONE")
    print(BAR)
    print(" 종합")
    print(BAR)
    print(f"  DARK 평균 {d:.1f}  /  NONE 평균 {no:.1f}  /  WARM 평균 {w:.1f}")
    print(f"  ▶ 개인화 효과(WARM−DARK) : {w - d:+.1f}점")
    ordered = d < no < w
    direction = d < w
    print(f"  방향성(DARK<WARM)        : {'✅ 기대대로' if direction else '❌ 반대/무효과'}")
    print(f"  단조성(DARK<NONE<WARM)   : {'✅' if ordered else '△ 부분적'}  (NONE이 중간인가)")
    print(BAR)
    print(" ※ '검색≠생성' 교훈: 효과가 작아도 그대로가 정직한 값.")


if __name__ == "__main__":
    main()
