"""RAG 시연 데모 — "AI는 한참 전 설정을 기억하는가?"

발표용. 한 세션에서:
  1) 핵심 설정(비밀)을 심고
  2) 무관한 잡담으로 대화창 밖으로 밀어낸 뒤
  3) 그 설정을 묻는다 → RAG 끄면(최근 대화만) 못 떠올리고, 켜면(의미검색) 정확히 끌어온다.

실행: backend 폴더에서
    python -m scripts.rag_demo        (conda nodevelture 환경, DB·GEMINI_API_KEY 필요)

서버 불필요(인프로세스 TestClient). 퀄리티가 아니라 "기억을 끌어오는지"를 눈으로 보여주는 용도.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio
import json
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.database import AsyncSessionLocal, engine
from app.models.user import User

SECRET = "민준은 사실 잠입 수사 중인 형사다. 정체를 숨기고 카페에서 일하는 척하고 있다."
FILLER = [
    "나는 따뜻한 커피를 한 모금 마신다.",
    "창밖에는 여전히 비가 내리고 있다.",
    "민준이 주문을 받으러 테이블로 다가온다.",
    "나는 메뉴판을 천천히 살펴본다.",
    "가게 안에 잔잔한 음악이 흐른다.",
]
PROBE = "문득 궁금해진다. 민준의 진짜 정체가 뭐였지?"

BAR = "=" * 64


def _ask(c, sid, text, use_rag):
    """/stream 호출 → event: reply 파싱해 dict 반환."""
    out = {"narration": "", "dialogue": "", "memories": []}
    with c.stream("GET", f"/api/v1/chats/{sid}/stream", params={
        "content": text, "character_id": "hanyeoreum",
        "world_context": "비 오는 카페", "mode": "author",
        "use_rag": str(use_rag).lower(),
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


def _box(title, mems, ans):
    print(f"┌─ {title} " + "─" * max(0, 50 - len(title)))
    if mems:
        print("│ 💭 떠올린 기억:")
        for m in mems:
            print(f"│    • {m[:60]}")
    else:
        print("│ 💭 떠올린 기억: (없음)")
    reply = (ans["narration"] + " " + (f'"{ans["dialogue"]}"' if ans["dialogue"] else "")).strip()
    print(f"│ 🤖 AI: {reply[:160]}")
    print("└" + "─" * 52)


async def _make_user():
    suffix = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        u = User(username=f"ragdemo_{suffix}", email=f"ragdemo_{suffix}@t.com", hashed_password="x")
        s.add(u)
        await s.flush()
        uid = str(u.id)
        await s.commit()
    await engine.dispose()
    return uid


def main():
    uid = asyncio.run(_make_user())

    print(BAR)
    print(" NodeVelture RAG 시연 — \"AI는 한참 전 설정을 기억하는가?\"")
    print(BAR)

    with TestClient(app) as c:
        w = c.post(f"/api/v1/worlds/?user_id={uid}", json={
            "title": "잠입 수사", "description": "형사물", "genre": "추리",
            "setting": "비 오는 카페", "rules": "",
        }).json()["id"]
        p = c.post(f"/api/v1/worlds/{w}/characters/", json={
            "user_id": uid, "name": "나", "role": "protagonist",
            "personality": "평범한 손님", "prompt": "", "is_ai_controlled": False,
        }).json()["id"]
        c.post(f"/api/v1/worlds/{w}/characters/", json={
            "user_id": uid, "name": "민준", "role": "supporting",
            "personality": "무뚝뚝한 알바생", "prompt": "", "is_ai_controlled": True,
        })
        sid = c.post("/api/v1/sessions/", json={
            "world_id": w, "user_id": uid, "protagonist_id": p, "author_id": 3,
        }).json()["id"]

        def send(text):
            c.post(f"/api/v1/chats/{sid}/messages", json={"content": text})
            _ask(c, sid, text, use_rag=True)

        print(f"\n[턴 1] 🔑 핵심 설정 심기:\n   \"{SECRET}\"")
        send(SECRET)

        print(f"\n[턴 2~{len(FILLER)+1}] 무관한 잡담으로 대화창 밖으로 밀어내기...")
        for f in FILLER:
            print(f"   - {f}")
            send(f)

        total_turns = len(FILLER) + 2
        print(f"\n[질문] (지금은 {total_turns}턴째 — 비밀은 {total_turns-1}턴 전) \n   \"{PROBE}\"\n")

        # send 질문 메시지(둘 다 같은 입력) 후, RAG off/on 두 번 생성 비교
        c.post(f"/api/v1/chats/{sid}/messages", json={"content": PROBE})
        off = _ask(c, sid, PROBE, use_rag=False)
        on = _ask(c, sid, PROBE, use_rag=True)

    _box("❌ RAG 끄면 (최근 대화만)", off["memories"], off)
    _box("✅ RAG 켜면 (의미 검색)", on["memories"], on)

    hit = any("형사" in m or "잠입" in m for m in on["memories"])
    print()
    if hit:
        print(f"판정: ✅ RAG가 {total_turns-1}턴 전 설정('잠입 형사')을 검색해 일관성 유지")
    else:
        print("판정: ⚠️ 관련 기억을 못 끌어옴 — 턴 수/임계값 점검 필요")
    print(BAR)


if __name__ == "__main__":
    main()
