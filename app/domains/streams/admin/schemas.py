from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.domains.streams.models import (
    AccessLevel,
    CategoryType,
    ChannelType,
    LatencyMode,
    StreamStatus,
)

# 모든 AWS 통신(In/Out)은 CamelCase, 서버 내부 로직은 snake_case
COMMON_CONFIG = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    from_attributes=True,
)


class ChannelConfig(BaseModel):
    """IVS 채널 생성 상세 설정"""

    model_config = COMMON_CONFIG
    latency_mode: LatencyMode = Field(default=LatencyMode.LOW)
    channel_type: ChannelType = Field(default=ChannelType.STANDARD, alias="type")


class StreamLiveMetrics(BaseModel):
    model_config = COMMON_CONFIG
    health: str = Field(..., description="스트림 건강 상태 (HEALTHY, STARVING, UNKNOWN)")
    viewer_count: int = Field(..., description="현재 동시 시청자 수")
    start_time: datetime | None = Field(None, description="방송 시작 시각")
    state: str = Field(..., description="LIVE 상태")


class IVSUpdateConfig(BaseModel):
    model_config = COMMON_CONFIG
    latency_mode: LatencyMode | None = None
    channel_type: ChannelType | None = Field(None, alias="type")


class StreamIngestInfo(BaseModel):
    model_config = COMMON_CONFIG
    ingest_endpoint: str = Field(..., description="RTMP 서버 주소")
    stream_key: str = Field(..., alias="value", description="복호화된 스트림 키")  # AWS는 value


class IVSChannelSummary(BaseModel):
    """AWS IVS 채널 정보 요약"""

    model_config = COMMON_CONFIG
    arn: str
    ingest_endpoint: str
    playback_url: str
    latency_mode: LatencyMode
    type: ChannelType


# ==================== 요청 스키마 ====================
class ConcertCreateRequest(BaseModel):
    """콘서트 생성 요청 스키마"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )  # 프론트에서 오는 camel -> snake
    category: CategoryType
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    thumbnail_url: str | None = None


class SessionCreateRequest(BaseModel):
    """콘서트 세션 생성 요청 스키마"""

    model_config = COMMON_CONFIG
    session_name: str = Field(..., min_length=1, max_length=100)
    start_at: datetime
    end_at: datetime | None = None
    access_level: AccessLevel = Field(default=AccessLevel.PUBLIC)
    is_test: bool = Field(default=False)

    # 검색/필터링을 위한 아티스트 연결
    artist_ids: list[int] = Field(default_factory=list, description="출연 아티스트 ID 목록")

    # 채널 설정 (기본값 제공)
    channel_config: ChannelConfig = Field(default_factory=ChannelConfig)


class SessionUpdateRequest(BaseModel):
    """세션 수정 요청 스키마"""

    model_config = COMMON_CONFIG
    session_name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    access_level: AccessLevel | None = None
    is_test: bool | None = None
    artist_ids: list[int] | None = None  # 라인업
    channel_config: IVSUpdateConfig | None = None  # IVS  채널 수정


# ==================== 응답 스키마 ====================
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


class SessionResponse(BaseModel):
    """세션 응답"""

    model_config = COMMON_CONFIG
    id: int = Field(..., description="내부 세션 ID")
    session_name: str
    access_level: AccessLevel
    start_at: datetime

    status: StreamStatus

    # 인프라 정보는 별도 객체로 분리
    channel: IVSChannelSummary | None = None
    stream_key: str | None = Field(
        None, description="생성 시에만 일회성으로 노출되는 스트림 키", alias="value"
    )


class StreamIngestResponse(BaseModel):
    """송출 OBS 응답"""

    model_config = COMMON_CONFIG
    session_id: int
    is_live: bool
    concert_title: str
    ingest_info: StreamIngestInfo
    playback_url: str
    playback_token: str | None = None
    live_metrics: StreamLiveMetrics | None = None
