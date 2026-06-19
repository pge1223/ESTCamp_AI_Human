"""응답 엔진 호출 로그 요약 (발표 제출용).

api_logs 테이블을 집계해 ① 전체 사용량 ② 엔진(model)별 호출수·토큰·비용
③ 1콜 평균 비용 을 출력한다. 비용은 적재 시 calc_cost로 계산된 total_cost 합.

실행: conda run -n nodevelture python -m scripts.usage_summary
"""
import asyncio

from sqlalchemy import text

from app.database import engine


async def main() -> None:
    async with engine.connect() as c:
        total = (await c.execute(text(
            "SELECT count(*) calls, coalesce(sum(prompt_tokens),0) pt, "
            "coalesce(sum(completion_tokens),0) ct, coalesce(sum(total_cost),0) cost "
            "FROM api_logs"
        ))).one()
        calls, pt, ct, cost = total
        print("=== 전체 ===")
        print(f"총 호출수      : {calls:,}")
        print(f"prompt tokens  : {pt:,}")
        print(f"completion tok : {ct:,}")
        print(f"총 토큰        : {pt + ct:,}")
        print(f"총 비용(USD)   : ${cost:.4f}")
        if calls:
            print(f"1콜 평균 비용  : ${cost / calls:.6f}")
            print(f"1콜 평균 토큰  : {(pt + ct) / calls:,.0f}")

        print("\n=== 엔진(model)별 ===")
        rows = (await c.execute(text(
            "SELECT coalesce(nullif(model_used,''),'(unknown)') m, count(*) calls, "
            "coalesce(sum(prompt_tokens),0) pt, coalesce(sum(completion_tokens),0) ct, "
            "coalesce(sum(total_cost),0) cost "
            "FROM api_logs GROUP BY 1 ORDER BY calls DESC"
        ))).all()
        print(f"{'model':<26}{'calls':>8}{'tokens':>12}{'cost($)':>12}{'avg/call($)':>14}")
        for m, mc, mpt, mct, mcost in rows:
            avg = mcost / mc if mc else 0
            print(f"{m:<26}{mc:>8,}{mpt + mct:>12,}{mcost:>12.4f}{avg:>14.6f}")

        print("\n=== 엔드포인트별(상위 10) ===")
        eps = (await c.execute(text(
            "SELECT endpoint, count(*) calls, coalesce(sum(total_cost),0) cost "
            "FROM api_logs GROUP BY endpoint ORDER BY calls DESC LIMIT 10"
        ))).all()
        for ep, ec, ecost in eps:
            print(f"{ep:<40}{ec:>6,} calls  ${ecost:.4f}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
