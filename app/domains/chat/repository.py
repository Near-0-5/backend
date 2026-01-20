import json
from typing import Any

from app.core.redis import redis_client
from app.domains.chat.schemas import ServerEvent

# <<< (CHANGED) 운영에서는 env/settings로 빼는 게 정답. 지금은 상수로 두되 의미가 드러나게.
CHAT_MAX_MESSAGES = 100  # 최근 N개만 유지
CHAT_TTL_SECONDS = 60 * 60 * 24  # 1일 TTL
RATE_LIMIT_SECONDS = 2  # 메시지 2초에 1개


def _chat_key(room_id: str) -> str:
    return f"chat:{room_id}"


async def rate_limit_ok(room_id: str, user_id: str) -> bool:
    key = f"chat:rate:{room_id}:{user_id}"
    return bool(await redis_client.set(key, "1", ex=RATE_LIMIT_SECONDS, nx=True))


async def append_chat_message(room_id: str, evt: dict[str, Any]) -> None:
    """
    채팅 이벤트를 Redis에 저장
    """
    validated_evt = ServerEvent.model_validate(evt)
    key = _chat_key(room_id)
    payload = validated_evt.model_dump_json()

    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.rpush(key, payload)
        pipe.ltrim(key, -CHAT_MAX_MESSAGES, -1)
        pipe.expire(key, CHAT_TTL_SECONDS)
        await pipe.execute()


async def get_recent_messages(room_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Redis에서 특정 room_id의 최근 채팅 이벤트 목록을 조회한다.
    """
    key = _chat_key(room_id)
    limit = max(1, min(limit, CHAT_MAX_MESSAGES))

    try:
        raw = await redis_client.lrange(key, -limit, -1)
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        try:
            # <<< (NEW) bytes/str 혼재 대비
            if isinstance(item, (bytes, bytearray)):
                item = item.decode("utf-8", errors="strict")
            out.append(json.loads(item))
        except Exception:
            continue
    return out