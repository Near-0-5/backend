from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.streams.models import CategoryType, StreamStatus


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SessionItem(BaseSchema):
    """목록 조회 응답"""

    id: int
    concert_title: str
    session_name: str
    thumbnail_url: str | None
    category: CategoryType
    status: StreamStatus
    start_at: datetime


class SessionListResponse(BaseSchema):
    items: list[SessionItem]
    next_cursor: int | None
