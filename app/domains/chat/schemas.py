from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class ClientMessage(BaseModel):
    type: Literal["message"] = "message"
    text: str = Field(min_length=1, max_length=500)

class ServerEvent(BaseModel):
    type: Literal["message"] = "message"
    room_id: str
    user_id: str
    test: str
    ts: str
    message_id: Optional[str] = None