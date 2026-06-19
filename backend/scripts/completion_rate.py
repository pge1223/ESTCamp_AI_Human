"""완료율 측정 — 세션 상태 집계로 Task Completion Rate 산출.

정량 평가표의 '완료율(세션 정상종료)' 행을 채운다.
  완료율(%) = completed / (active + paused + completed) × 100

실행: backend 폴더에서
    python -m scripts.completion_rate     (conda nodevelture, .env DB 필요)
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio

from sqlalchemy import select, func

from app.database import AsyncSessionLocal
import app.models  # noqa: F401  (전체 모델 등록 — 관계 해석용)
from app.models.session import Session


async def main():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Session.status, func.count(Session.id)).group_by(Session.status)
        )).all()

    counts = {str(getattr(st, "value", st)): n for st, n in rows}
    total = sum(counts.values())
    completed = counts.get("completed", 0)
    rate = (completed / total * 100) if total else 0.0

    print("=== 세션 완료율 (Task Completion Rate) ===")
    for k in ("active", "paused", "completed"):
        print(f"  {k:<10}: {counts.get(k, 0)}")
    print(f"  {'total':<10}: {total}")
    print()
    print(f"완료율 = completed/total = {completed}/{total} = {rate:.1f}%   (목표 ≥80%)")
    if total == 0:
        print("※ 세션이 없습니다. 데모 세션을 몇 개 만든 뒤 다시 측정하세요.")


if __name__ == "__main__":
    asyncio.run(main())
