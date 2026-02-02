from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.domains.concerts.models import CategoryType
from app.domains.streams.admin.schemas import SessionResponse


class ConcertCreateRequest(BaseModel):
    """콘서트 생성 요청 스키마"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )  # 프론트에서 오는 camel -> snake
    category: CategoryType
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    thumbnail_url: str | None = None


class ConcertResponse(BaseModel):
    """콘서트 생성 응답"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )
    id: int
    title: str
    category: CategoryType
    description: str | None = None
    thumbnail_url: str | None = Field(None)
    created_at: datetime


class ConcertDetailResponse(ConcertResponse):
    """콘서트 상세 응답"""

    sessions: list[SessionResponse] = Field(default_factory=list)
