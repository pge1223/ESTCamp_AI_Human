"""일관성 검수 시연 데모 (F-QC-01).

확립된 설정과 새 내용을 비교해 모순을 잡아내는지 보여준다.
  - 모순 케이스(형사 ↔ 의사) → 위반으로 잡아야 함
  - 정상 케이스 → 통과해야 함

실행: backend 폴더에서
    python -m scripts.consistency_demo   (conda nodevelture 환경, GEMINI/GROQ 키 필요)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio
from app.services import consistency

FACTS = """제목: 잠입 수사
장르: 추리
배경: 비 오는 카페
[등장인물]
- 민준 (supporting): 잠입 수사 중인 형사. 정체를 숨기고 카페 알바로 위장 중이다.
[관련 기억]
- 민준은 사실 잠입 수사 중인 형사다. 아무도 그의 정체를 모른다."""

CASES = [
    ("모순", "민준은 사실 병원에서 일하는 외과 의사였다. 그는 흰 가운을 입고 수술실로 향했다."),
    ("정상", "민준은 주문서를 받아들고 무뚝뚝하게 고개를 끄덕였다. 빗소리가 창을 두드렸다."),
]

BAR = "=" * 60


async def main():
    print(BAR)
    print(" NodeVelture 일관성 검수 시연 (F-QC-01)")
    print(BAR)
    print("\n[확립된 설정]")
    for line in FACTS.splitlines():
        print("  " + line)

    for label, text in CASES:
        print(f"\n── [{label} 케이스] 검수 대상 ──")
        print(f"  \"{text}\"")
        result = await consistency.check(FACTS, text)
        mark = "✅ 일관성 OK" if result["consistent"] else "🚨 모순 발견"
        print(f"  → {mark}")
        for v in result["violations"]:
            print(f"     • 설정: {v.get('established','')}")
            print(f"       충돌: {v.get('conflict','')}  [{v.get('severity','')}]")
    print("\n" + BAR)


if __name__ == "__main__":
    asyncio.run(main())
