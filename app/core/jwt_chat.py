from __future__ import annotations

import time
from typing import Any

import jwt

CHAT_JWT_SECRET = "CHANGE_ME"
CHAT_JWT_ALG = "HS256"
CHAT_ACCESS_TTL_SEC = 10 * 60


def issue_chat_token(*, room_id: str, user_id: str) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "typ": "chat",
        "room_id": room_id,
        "user_id": user_id,
        "iat": now,
        "exp": now + CHAT_ACCESS_TTL_SEC,
    }
    return jwt.encode(payload, CHAT_JWT_SECRET, algorithm=CHAT_JWT_ALG)


def verify_chat_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, CHAT_JWT_SECRET, algorithms=[CHAT_JWT_ALG])