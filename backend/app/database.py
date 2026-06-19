from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def _prepare_db_url(url: str) -> tuple[str, dict]:
    """Neon/클라우드 URL을 asyncpg 호환 형식으로 변환.
    - postgresql:// → postgresql+asyncpg://
    - ?sslmode=require 제거 → connect_args={"ssl": "require"} 로 이관
    """
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.split("://", 1)[1]

    connect_args: dict = {}
    if "sslmode=require" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        new_query = urlencode({k: v[0] for k, v in params.items()})
        url = urlunparse(parsed._replace(query=new_query))
        connect_args["ssl"] = "require"

    return url, connect_args


_db_url, _connect_args = _prepare_db_url(settings.DATABASE_URL)

# PostgreSQL
engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,    # 사용 전 커넥션 생존 확인 → 죽은 커넥션 자동 교체
    pool_recycle=1800,     # 30분 지난 커넥션은 재생성 (유휴 끊김 방지)
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        
