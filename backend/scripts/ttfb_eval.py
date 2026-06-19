"""TTFB 측정 — 채팅 스트림의 '첫 응답 바이트까지 걸린 시간'을 N회 재서 p50/p95 산출.

정량 평가표의 'TTFB(응답 첫 바이트)' 행을 채운다. (목표 ≤1.5s)

  - 라이브 백엔드(Cloud Run)의 스트림 엔드포인트를 실제 호출해 첫 청크 도착 시각을 잰다.
  - 워밍업 1회 후 N회 측정(콜드스타트 제외). p50=중앙값, p95=꼬리지연.

⚠️ 스트림은 세션에 대화 턴을 추가한다 → **버려도 되는 테스트 세션 id**를 쓸 것.

실행: backend 폴더에서
    python -m scripts.ttfb_eval <session_id> [횟수=8]
  또는 환경변수:  EVAL_SESSION_ID=... EVAL_API_BASE=... python -m scripts.ttfb_eval
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import time
import asyncio
import statistics

import httpx

API = os.getenv("EVAL_API_BASE", "https://nodevelture-api-958641405309.us-central1.run.app/api/v1")
SESSION = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("EVAL_SESSION_ID", "")).strip()
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
PROMPTS = ["오랜만이네.", "그래서 어떻게 됐어?", "계속 얘기해줘.", "음… 그렇구나.",
           "조금 더 자세히.", "그 다음은?", "왜 그랬을까.", "이제 어떡하지."]


async def measure_ttfb(client: httpx.AsyncClient, content: str):
    """스트림 호출 → 첫 청크 도착까지 초. 실패 시 None."""
    params = {"content": content, "character_id": "kimdohyeon", "mode": "author", "world_context": ""}
    t0 = time.perf_counter()
    try:
        async with client.stream("GET", f"{API}/chats/{SESSION}/stream", params=params, timeout=60) as r:
            async for _chunk in r.aiter_bytes():
                if _chunk:
                    return time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        print(f"   (요청 실패: {e})")
    return None


async def main():
    if not SESSION:
        print("사용법: python -m scripts.ttfb_eval <session_id> [횟수]")
        print("  (버려도 되는 테스트 세션 id 권장 — 측정이 대화 턴을 추가함)")
        return
    print(f"대상: {API}/chats/{SESSION}/stream   (워밍업 1회 + 측정 {N}회)")
    async with httpx.AsyncClient() as client:
        await measure_ttfb(client, "워밍업")  # 콜드스타트 제외
        ttfbs = []
        for i in range(N):
            t = await measure_ttfb(client, PROMPTS[i % len(PROMPTS)])
            if t is not None:
                ttfbs.append(t)
                print(f"  {i + 1:>2}/{N}: {t:.2f}s")

    if not ttfbs:
        print("측정 실패 — 세션 id/네트워크 확인.")
        return
    ttfbs.sort()
    p95 = ttfbs[min(len(ttfbs) - 1, int(round(len(ttfbs) * 0.95)) - 1)]
    print("\n=== TTFB 결과 (n=%d) ===" % len(ttfbs))
    print(f"  min : {ttfbs[0]:.2f}s")
    print(f"  p50 : {statistics.median(ttfbs):.2f}s")
    print(f"  p95 : {p95:.2f}s")
    print(f"  max : {ttfbs[-1]:.2f}s")
    print(f"  목표 ≤1.5s → {'✅ 충족' if statistics.median(ttfbs) <= 1.5 else '⚠️ 초과(워밍업/리전 개선 여지)'}")


if __name__ == "__main__":
    asyncio.run(main())
