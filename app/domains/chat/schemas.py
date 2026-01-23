from typing import Literal

from pydantic import BaseModel, Field


class ClientMessage(BaseModel):
    type: Literal["message"] = "message"
    text: str = Field(min_length=1, max_length=500)


class ServerEvent(BaseModel):
    type: Literal["message", "system", "recent"] = "message"
    room_id: str
    user_id: str
    text: str
    ts: str
    message_id: str | None = None
