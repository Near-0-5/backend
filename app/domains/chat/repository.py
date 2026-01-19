import json
from typing import Any

from app.core.redis import redis_client
from app.domains.chat.schemas import ServerEvent

#! 환경변수로 빼야하나 고민 중
CHAT_MAX_MESSAGES = 100  # 최근 100개만 유지
CHAT_TTL_SECONDS = 60 * 60 * 24  # 1일 TTL
RATE_LIMIT_SECONDS = 2


def _chat_key(room_id: str) -> str:
    return f"chat:{room_id}"


async def rate_limit_ok(room_id: str, user_id: str) -> bool:
    key = f"chat:rate:{room_id}:{user_id}"
    return bool(await redis_client.set(key, "1", ex=RATE_LIMIT_SECONDS, nx=True))


async def append_chat_message(room_id: str, evt: dict[str, Any]) -> None:
    """
    채팅 이벤트(ServerEvent)를 Redis에 저장.

    Args:
        room_id (str): 채팅방 식별자(키 생성에 사용).
        evt (dict[str, Any]): ServerEvent 형식의 이벤트 payload(dict).

    Flow:
        1) evt를 ServerEvent 스키마로 검증(model_validate)한다.
        2) room_id로 Redis key(chat:{room_id})를 생성한다.
        3) 검증된 이벤트를 JSON 문자열로 직렬화(model_dump_json)한다.
        4) pipeline으로 RPUSH/LTRIM/EXPIRE를 묶어서 실행한다.
            - RPUSH: 리스트 끝에 추가
            - LTRIM: 최근 CHAT_MAX_MESSAGES개만 유지
            - EXPIRE: TTL 설정(슬라이딩 TTL)

    Note:
        - 현재는 메시지 저장 시마다 EXPIRE를 호출하는 "슬라이딩 TTL" 방식임.
        - 운영 정책에 따라 방 종료 시점에만 TTL을 거는 방식으로 변경할 수도 있음.
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

    Args:
        room_id (str): 채팅방 식별자.
        limit (int): 조회 개수(1~CHAT_MAX_MESSAGES 범위로 보정).

    Flow:
        1) room_id로 Redis key(chat:{room_id})를 생성한다.
        2) limit 값을 1~CHAT_MAX_MESSAGES 범위로 보정한다.
        3) LRANGE로 리스트의 뒤에서 limit개(-limit ~ -1)를 조회한다.
        4) 각 항목(JSON 문자열)을 json.loads로 dict로 역직렬화하여 리스트로 만든다.
            - 역직렬화 실패 항목은 스킵한다.

    Returns:
        list[dict[str, Any]]: ServerEvent 형태의 dict 리스트.
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
            out.append(json.loads(item))
        except Exception:
            continue
    return out
