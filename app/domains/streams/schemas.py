from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.streams.models import AccessLevel, CategoryType, ChannelType, LatencyMode


class ChannelConfig(BaseModel):
    """IVS 채널 생성 상세 설정"""

    latency_mode: LatencyMode = Field(default=LatencyMode.LOW)
    channel_type: ChannelType = Field(default=ChannelType.STANDARD)


class ConcertCreateRequest(BaseModel):
    """콘서트 생성 요청 스키마"""

    category: CategoryType
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    thumbnail_url: str | None = None
    access_level: AccessLevel = Field(default=AccessLevel.PUBLIC)
    start_at: datetime
    end_at: datetime | None = None

    # 채널 설정 (기본값 제공)
    channel_config: ChannelConfig = Field(default_factory=ChannelConfig)


class ConcertResponse(BaseModel):
    """콘서트 생성 완료 응답"""

    id: int
    title: str
    access_level: AccessLevel
    created_at: datetime

    class Config:
        from_attributes = True
