import redis.asyncio as redis
from app.core.config import settings


redis_client: redis.Redis = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)