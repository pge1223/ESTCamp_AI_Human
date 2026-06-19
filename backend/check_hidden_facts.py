import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

SESSION_ID = "0e1bdc51-7d02-426e-90d0-acdc4f1bd207"
DATABASE_URL = "postgresql+asyncpg://nodevelture:nodevelture@localhost:5432/nodevelture"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with AsyncSession(engine) as db:
        r = await db.execute(text("SELECT world_id FROM sessions WHERE id = :sid"), {"sid": SESSION_ID})
        row = r.fetchone()
        if not row:
            print("세션 없음")
            return
        world_id = str(row[0])
        print("world_id:", world_id)
        r2 = await db.execute(text("SELECT hidden_facts FROM worlds WHERE id = :wid"), {"wid": world_id})
        row2 = r2.fetchone()
        print("hidden_facts:", row2[0] if row2 else "없음")

asyncio.run(main())
