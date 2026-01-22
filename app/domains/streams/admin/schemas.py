from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.streams.models import AccessLevel, CategoryType, ChannelType, LatencyMode


class ChannelConfig(BaseModel):
    """IVS 채널 생성 상세 설정"""

    latency_mode: LatencyMode = Field(default=LatencyMode.LOW)
    channel_type: ChannelType = Field(default=ChannelType.STANDARD)


class StreamLiveMetrics(BaseModel):
    health: str = Field(..., description="스트림 건강 상태 (HEALTHY...)")
    viewerCount: int = Field(..., description="현재 동시 시청자 수")
    startTime: datetime | None = Field(None, description="방송 시작 시각")


class StreamIngestInfo(BaseModel):
    ingestEndpoint: str = Field(..., description="RTMP 서버 주소")
    streamKey: str = Field(..., description="복호화된 스트림 키")


# ==================== 요청 스키마 ====================
class ConcertCreateRequest(BaseModel):
    """콘서트 생성 요청 스키마"""

    category: CategoryType
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    thumbnail_url: str | None = None

    model_config = {"extra": "forbid"}


class SessionCreateRequest(BaseModel):
    """콘서트 세션 생성 요청 스키마"""

    session_name: str = Field(..., min_length=1, max_length=100)
    start_at: datetime
    end_at: datetime | None = None
    access_level: AccessLevel = Field(default=AccessLevel.PUBLIC)
    is_test: bool = Field(default=False)

    # 검색/필터링을 위한 아티스트 연결
    artist_ids: list[int] = Field(default_factory=list, description="출연 아티스트 ID 목록")

    # 채널 설정 (기본값 제공)
    channel_config: ChannelConfig = Field(default_factory=ChannelConfig)


# ==================== 응답 스키마 ====================


class IVSChannelSummary(BaseModel):
    """AWS IVS 채널 정보 요약"""

    channel_arn: str
    ingest_endpoint: str
    playback_url: str
    latency_mode: LatencyMode
    channel_type: ChannelType


class ConcertResponse(BaseModel):
    """콘서트 생성 최종 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: CategoryType
    description: str | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    """세션 생성 최종 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="내부 세션 ID")
    session_name: str
    access_level: AccessLevel
    start_at: datetime

    # 인프라 정보는 별도 객체로 분리
    channel: IVSChannelSummary | None = None
    stream_key: str | None = Field(None, description="생성 시에만 일회성으로 노출되는 스트림 키")


class StreamIngestResponse(BaseModel):
    sessionId: int
    isLive: bool
    concertTitle: str
    ingestInfo: StreamIngestInfo
    playbackUrl: str
    liveMetrics: StreamLiveMetrics | None = None
