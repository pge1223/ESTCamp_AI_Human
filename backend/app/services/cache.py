import hashlib
import json
import logging
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis TTL 캐시 서비스"""

    def __init__(self):
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._client

    def _key(self, namespace: str, payload: dict) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{namespace}:{digest}"

    async def get(self, namespace: str, payload: dict) -> str | None:
        try:
            client = await self._get_client()
            return await client.get(self._key(namespace, payload))
        except Exception as e:
            logger.warning("캐시 조회 실패: %s", e)
            return None

    async def set(self, namespace: str, payload: dict, value: str, ttl: int | None = None) -> None:
        try:
            client = await self._get_client()
            await client.setex(self._key(namespace, payload), ttl or settings.CACHE_TTL, value)
        except Exception as e:
            logger.warning("캐시 저장 실패: %s", e)
