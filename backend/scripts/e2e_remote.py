"""백엔드 원격(Remote) E2E — 배포된 Cloud Run 리비전에 실제 HTTP로 전체 흐름을 태운다.

e2e_smoke.py(인프로세스)와 달리, 살아있는 서버에 네트워크로 요청한다:
  유저 시드(로컬 DB 세션) → [같은 DB 확인] → 세계관 → 등장인물 → 세션 → 메시지
  → AI 스트리밍(delta/reply/audio) → 채팅 종료 → 소설 변환 → 소설 조회

실행: backend 폴더에서  python -m scripts.e2e_remote
  BASE_URL 환경변수로 대상 지정(기본=프로덕션 Cloud Run).
유저는 /register 버그 때문에 로컬 DB 세션으로 직접 삽입한다. 로컬 .env DATABASE_URL이
배포 서버와 같은 Neon이어야 라이브 API가 그 유저를 인식한다(스크립트가 자동 확인).
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import json
import uuid
import asyncio

import httpx

from app.database import AsyncSessionLocal, engine
from app.models.user import User

BASE_URL = os.environ.get("BASE_URL", "https://nodevelture-api-ovjsg44f3q-uc.a.run.app").rstrip("/")
API = f"{BASE_URL}/api/v1"

ok, ng = "✅", "❌"
passed, failed = 0, 0


def show(n, label, resp, *, expect=(200, 201)):
    global passed, failed
    good = resp.status_code in expect
    print(f"[{n}] {label}: {ok if good else ng} {resp.status_code}")
    if good:
        passed += 1
    else:
        failed += 1
        print("    →", str(resp.text)[:300])
    return good


suffix = uuid.uuid4().hex[:8]
email = f"e2e_remote_{suffix}@test.com"


async def _make_user():
    async with AsyncSessionLocal() as s:
        u = User(username=f"e2e_remote_{suffix}", email=email, hashed_password="x")
        s.add(u)
        await s.flush()
        uid = str(u.id)
        await s.commit()
    await engine.dispose()
    return uid


def main():
    global passed, failed
    print(f"=== 원격 E2E 대상: {BASE_URL} ===")

    # 0) health
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{BASE_URL}/health")
        show(0, "health", r)

    # 1) 유저 시드(로컬 DB)
    user_id = asyncio.run(_make_user())
    print(f"[1] 유저 시드(로컬 DB 직접 삽입): {ok} {user_id}")

    with httpx.Client(timeout=90) as c:
        # 1b) 같은 DB 확인 — 라이브 API가 방금 시드한 유저를 보는가
        r = c.get(f"{API}/users/{user_id}")
        same_db = r.status_code == 200
        print(f"[1b] 라이브 API가 시드 유저 인식(=같은 Neon DB): {ok if same_db else ng} {r.status_code}")
        if not same_db:
            print("    ⚠️ 로컬 .env DATABASE_URL과 배포 서버 DB가 다릅니다. 이후 단계는 의미 없으니 중단.")
            return

        # 2) 세계관
        r = c.post(f"{API}/worlds/?user_id={user_id}", json={
            "title": "원격 E2E 세계관", "description": "원격 테스트", "genre": "로맨스",
            "setting": "비 오는 카페", "rules": "",
        })
        show(2, "세계관 생성", r)
        world_id = r.json()["id"]

        # 3) 등장인물
        r = c.post(f"{API}/worlds/{world_id}/characters/", json={
            "user_id": user_id, "name": "나", "role": "protagonist",
            "personality": "평범", "prompt": "", "is_ai_controlled": False,
        })
        show(3, "주인공 생성", r)
        protagonist_id = r.json()["id"]

        r = c.post(f"{API}/worlds/{world_id}/characters/", json={
            "user_id": user_id, "name": "민준", "role": "supporting",
            "personality": "차가운 알바생", "prompt": "차갑고 무뚝뚝하게 반응한다", "is_ai_controlled": True,
        })
        show("3b", "조연 생성", r)

        # 4) 세션
        r = c.post(f"{API}/sessions/", json={
            "world_id": world_id, "user_id": user_id, "protagonist_id": protagonist_id,
            "author_id": 3,
        })
        show(4, "세션 시작", r)
        session_id = r.json()["id"]

        # 5) 메시지
        content = "비 오는 날 카페에서 누군가를 기다리고 있다."
        r = c.post(f"{API}/chats/{session_id}/messages", json={
            "content": content, "character_id": "hanyeoreum",
            "world_context": "비 오는 카페", "mode": "author",
        })
        show(5, "메시지 전송", r, expect=(201,))

        # 6) AI 스트리밍 — delta/reply/audio 이벤트 카운트
        got, n_delta, n_reply, n_audio = "", 0, 0, 0
        with c.stream("GET", f"{API}/chats/{session_id}/stream", params={
            "content": content, "character_id": "hanyeoreum",
            "world_context": "비 오는 카페", "mode": "author",
        }) as resp:
            cur_event = ""
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    cur_event = line[6:].strip()
                    if cur_event == "delta":
                        n_delta += 1
                    elif cur_event == "reply":
                        n_reply += 1
                    elif cur_event == "audio":
                        n_audio += 1
                elif line.startswith("data:"):
                    try:
                        d = json.loads(line[5:].strip())
                        if cur_event == "reply":
                            got += d.get("narration", "") + d.get("dialogue", "")
                        if "error" in d:
                            print("    LLM 오류:", str(d["error"])[:200])
                    except Exception:
                        pass
        stream_ok = bool(got)
        print(f"[6] AI 스트리밍: {ok if stream_ok else ng} reply {len(got)}자 "
              f"(delta={n_delta} · reply={n_reply} · audio={n_audio})")
        if stream_ok:
            passed += 1
            print("    앞부분:", got[:90].replace("\n", " "))
        else:
            failed += 1

        # 7) 채팅 종료
        r = c.patch(f"{API}/sessions/{session_id}/complete")
        show(7, "채팅 종료", r)

        # 8) 소설 변환
        r = c.post(f"{API}/sessions/{session_id}/novel/generate")
        show(8, "소설 변환", r, expect=(201,))
        if r.status_code == 201:
            print("    소설 앞부분:", str(r.json().get("content", ""))[:110].replace("\n", " "))

        # 9) 소설 조회
        r = c.get(f"{API}/sessions/{session_id}/novel")
        show(9, "소설 조회", r)

    print(f"\n=== 원격 E2E 완료 — 통과 {passed} / 실패 {failed} ===")


if __name__ == "__main__":
    main()
