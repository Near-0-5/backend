import json
from typing import Any

from app.core.redis import redis_client
from app.domains.chat.schemas import ServerEvent

CHAT_MAX_MESSAGES = 100 # 최근 100개만 유지
CHAT_TTL_SECONDS = 60 * 60 * 24 # 1일 TTL

def _chat_key(room_id: str) -> str:
    return f"chat:{room_id}"


async def append_chat_message(room_id: str, evt: dict[str, Any]) -> None:
    validated_evt = ServerEvent.model_validate(evt)
    key = _chat_key(room_id)
    payload = validated_evt.model_dump_json()

    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.rpush(key, payload)
        pipe.ltrim(key, -CHAT_MAX_MESSAGES, -1)
        pipe.expire(key, CHAT_TTL_SECONDS)
        await pipe.execute()


async def get_recent_messages(room_id: str, limit: int = 50) -> list[dict[str, Any]]:
    key = _chat_key(room_id)
    limit = max(1, min(limit, CHAT_MAX_MESSAGES))

    raw = await redis_client.lrange(key, -limit, -1)
    out: list[dict[str, Any]] = []
    for item in raw:
        try:
            out.append(json.loads(item))
        except Exception:
            continue
    return out
