"""백엔드 E2E 스모크 테스트 (인프로세스).

서버를 띄우지 않고 FastAPI TestClient로 전체 흐름을 한 번에 통과시킨다:
  유저 → 세계관 → 등장인물 → 세션 → 메시지 → AI 스트리밍 → 채팅 종료 → 소설 변환

실행: backend 폴더에서  python -m scripts.e2e_smoke   (conda nodevelture 환경)
DB(도커 5433)와 GEMINI_API_KEY 가 살아 있어야 한다. 퀄리티가 아니라 "끝까지 도는지"만 확인.

주의: TestClient 는 반드시 `with` 컨텍스트로 사용한다(단일 이벤트 루프 유지).
      안 그러면 요청마다 새 루프가 생겨 async 커넥션 풀이 깨진다.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 이모지/한글 출력
except Exception:
    pass

import asyncio
import json
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.database import AsyncSessionLocal, engine
from app.models.user import User

ok = "✅"
ng = "❌"


def show(n, label, resp, *, expect=(200, 201)):
    good = resp.status_code in expect
    print(f"[{n}] {label}: {ok if good else ng} {resp.status_code}")
    if not good:
        print("    →", str(resp.text)[:300])
    return good


# 1) 유저 — /register 는 passlib+bcrypt 버그로 막혀 있어 ORM 직접 삽입으로 우회
suffix = uuid.uuid4().hex[:8]
email = f"e2e_{suffix}@test.com"


async def _make_user():
    async with AsyncSessionLocal() as s:
        u = User(username=f"e2e_{suffix}", email=email, hashed_password="x")
        s.add(u)
        await s.flush()
        uid = str(u.id)
        await s.commit()
    # 이 루프에 묶인 풀 커넥션 제거 → 이후 TestClient가 자기 루프에서 새로 연결
    await engine.dispose()
    return uid


user_id = asyncio.run(_make_user())
print(f"[1] 유저 생성(직접 삽입): {ok} {user_id}")

with TestClient(app) as c:
    # 2) 세계관 (user_id 는 쿼리 파라미터)
    r = c.post(f"/api/v1/worlds/?user_id={user_id}", json={
        "title": "E2E 테스트 세계관", "description": "테스트", "genre": "로맨스",
        "setting": "비 오는 카페", "rules": "",
    })
    show(2, "세계관 생성", r)
    world_id = r.json()["id"]

    # 3) 등장인물 (주인공 + 조연)
    r = c.post(f"/api/v1/worlds/{world_id}/characters/", json={
        "user_id": user_id, "name": "나", "role": "protagonist",
        "personality": "평범", "prompt": "", "is_ai_controlled": False,
    })
    show(3, "주인공 생성", r)
    protagonist_id = r.json()["id"]

    r2 = c.post(f"/api/v1/worlds/{world_id}/characters/", json={
        "user_id": user_id, "name": "민준", "role": "supporting",
        "personality": "차가운 알바생", "prompt": "차갑고 무뚝뚝하게 반응한다", "is_ai_controlled": True,
    })
    show("3b", "조연 생성", r2)

    # 4) 세션(채팅) 시작 — session_id 가 곧 chat_id. author_id=3(한여름) 저장 검증
    r = c.post("/api/v1/sessions/", json={
        "world_id": world_id, "user_id": user_id, "protagonist_id": protagonist_id,
        "author_id": 3,
    })
    show(4, "세션(채팅) 시작", r)
    session_id = r.json()["id"]
    returned_author = r.json().get("author_id")
    print(f"[4b] author_id 저장/반환: {ok if returned_author == 3 else ng} (보냄=3, 받음={returned_author})")

    # 5) 메시지 전송
    payload = {
        "content": "비 오는 날 카페에서 누군가를 기다리고 있다.",
        "character_id": "hanyeoreum", "world_context": "비 오는 카페", "mode": "author",
    }
    r = c.post(f"/api/v1/chats/{session_id}/messages", json=payload)
    show(5, "메시지 전송", r, expect=(201,))

    # 6) AI 응답 (event: reply = narration/dialogue 구조화)
    got = ""
    with c.stream("GET", f"/api/v1/chats/{session_id}/stream", params={
        "content": payload["content"], "character_id": "hanyeoreum",
        "world_context": "비 오는 카페", "mode": "author",
    }) as resp:
        for line in resp.iter_lines():
            if line and line.startswith("data:"):
                try:
                    d = json.loads(line[5:].strip())
                    # 신 컨트랙트: narration/dialogue (구) 컨트랙트: text 둘 다 수용
                    got += d.get("narration", "") + d.get("dialogue", "") + d.get("text", "")
                    if "error" in d:
                        print("    LLM 오류:", d["error"][:200])
                except Exception:
                    pass
    print(f"[6] AI 응답(reply): {ok if got else ng} 응답 {len(got)}자")
    if got:
        print("    앞부분:", got[:100].replace("\n", " "))

    # 7) 채팅 종료 (세션 완료)
    r = c.patch(f"/api/v1/sessions/{session_id}/complete")
    show(7, "채팅 종료(세션 완료)", r)

    # 8) 소설 변환
    r = c.post(f"/api/v1/sessions/{session_id}/novel/generate")
    show(8, "소설 변환", r, expect=(201,))
    if r.status_code == 201:
        print("    소설 앞부분:", str(r.json().get("content", ""))[:120].replace("\n", " "))

    # 9) 소설 조회
    r = c.get(f"/api/v1/sessions/{session_id}/novel")
    show(9, "소설 조회", r)

print("\n=== E2E 완료 ===")
