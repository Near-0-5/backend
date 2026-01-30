from enum import Enum
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from tortoise import fields, models
from tortoise.fields import (
    ForeignKeyRelation,
    ManyToManyRelation,
    OneToOneRelation,
    ReverseRelation,
)

from app.core.config import settings

if TYPE_CHECKING:
    from app.domains.artists.models import Artist
    from app.domains.notifications.models import ConcertNoti


# 공연 장르 카테고리
class CategoryType(str, Enum):
    KPOP = "K-POP"
    TROT = "TROT"
    MUSICAL = "MUSICAL"
    BAND = "BAND"
    FAN_MEETING = "FAN_MEETING"
    KOREA_TOUR = "KOREA_TOUR"


# 방송 송출 상태
class StreamStatus(str, Enum):
    READY = "READY"
    LIVE = "LIVE"
    ENDED = "ENDED"


# VOD 처리 상태
class VodStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# AWS IVS 채널 타입
class ChannelType(str, Enum):
    STANDARD = "STANDARD"
    ADVANCED_SD = "ADVANCED_SD"
    ADVANCED_HD = "ADVANCED_HD"
    BASIC = "BASIC"


# 지연 시간 모드
class LatencyMode(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"


# 트랜스코딩 품질 프리셋 (Advanced 채널용)
class TranscodingPreset(str, Enum):
    HBD = "HBD"  # HIGHER_BANDWIDTH_DELIVERY
    CBD = "CBD"  # CONSTRAINED_BANDWIDTH_DELIVERY


# 방송 접근 권한
class AccessLevel(str, Enum):
    PUBLIC = "PUBLIC"  # 전체 공개
    ADMIN_ONLY = "ADMIN_ONLY"  # 관리자/테스트용
    SPECIFIC = "SPECIFIC"  # 특정 유저(결제 유저 등)


class Concert(models.Model):
    """
    공연 메타 데이터
    - 특정 Category에 속함
    """

    id = fields.BigIntField(primary_key=True)
    category = fields.CharEnumField(
        CategoryType, default=CategoryType.KPOP, db_index=True, description="장르(category)"
    )
    title = fields.CharField(max_length=100, description="공연 제목")
    thumbnail_url = fields.CharField(
        max_length=255, null=True, description="공연 썸네일 사진(포스터 등)"
    )
    description = fields.TextField(null=True, description="콘서트 소개 글")

    created_at = fields.DatetimeField(auto_now_add=True, description="생성시각")
    updated_at = fields.DatetimeField(auto_now=True, description="수정시각")

    if TYPE_CHECKING:
        sessions: ForeignKeyRelation["ConcertSession"]

    class Meta:
        table = "concerts"

    def __str__(self) -> str:
        return f"{self.title} (id={self.id})"


class ConcertSession(models.Model):
    """
    콘서트 회차별 정보
    - 모든 스트리밍세션과 VOD의 부모 테이블
    - 여러 출연진(ConcertArtist)를 가질 수 있음
    """

    id = fields.BigIntField(primary_key=True)
    concert: ForeignKeyRelation["Concert"] = fields.ForeignKeyField(
        "models.Concert", related_name="sessions"
    )

    # ConcertArtist를 통해 Artist와 다대다 관계 형성
    lineup: ManyToManyRelation["Artist"] = fields.ManyToManyField(
        "models.Artist",
        through="concert_artists",
        related_name="sessions",
        forward_key="artist_id",
        backward_key="session_id",
        description="이 공연에 참여하는 모든 출연진 목록",
    )

    session_name = fields.CharField(max_length=50, description="회차 명칭 (예: 1회차, 서울공연)")
    status = fields.CharEnumField(
        StreamStatus,
        max_length=20,
        default="READY",
        description="방송 통로 상태 (READY, LIVE, ENDED)",
    )
    access_level = fields.CharEnumField(
        AccessLevel, max_length=20, default=AccessLevel.PUBLIC, description="접근 권한"
    )
    is_test = fields.BooleanField(default=False, description="테스트/실제 구분")

    start_at = fields.DatetimeField(description="공연 예정 시각")
    end_at = fields.DatetimeField(null=True, description="종료 예정 시각")

    @property
    def is_live(self) -> bool:
        return self.status == StreamStatus.LIVE

    if TYPE_CHECKING:
        stream_channel: "StreamChannel"
        artist_mappings: ReverseRelation["ConcertArtist"]
        stream_sessions: ForeignKeyRelation["StreamSession"]
        vods: ForeignKeyRelation["StreamVod"]
        scheduled_notis: fields.ReverseRelation["ConcertNoti"]

    class Meta:
        table = "concert_sessions"

    def __str__(self) -> str:
        return f"{self.session_name} (id={self.id}, concert_id={self.concert.id})"


class ConcertArtist(models.Model):
    """
    콘서트-출연진 매핑 테이블
    - 콘서트에 출연하는 아티스트들 (N: M)
    - 공연별로 출연진 / 메인 출연진 여부 관리
    """

    id = fields.BigIntField(primary_key=True)
    artist: ForeignKeyRelation["Artist"] = fields.ForeignKeyField(
        "models.Artist",
        related_name="session_mappings",
        on_delete=fields.CASCADE,
        description="출연 아티스트 참조",
    )
    session: ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession",
        related_name="artist_mappings",
        on_delete=fields.CASCADE,
        description="연결된 공연 참조",
    )

    is_main = fields.BooleanField(default=True, description="해당 공연의 메인 출연진 여부")
    created_at = fields.DatetimeField(auto_now_add=True, description="출연 확정/등록 시각")

    class Meta:
        table = "concert_artists"
        unique_together = ("artist", "session")  # 중복 출연 등록 방지

    def __str__(self) -> str:
        return f"session_id={self.session.id} artist_id={self.artist.id}"


class StreamChannel(models.Model):
    """
    AWS IVS 채널 설정 관리 테이블
    - 각 공연(Concert)에 할당된 방송 정보 (1:1)
    - 송출을 위한 스트림 키(암호화), 시청을 위한 재생 URL 관리
    """

    id = fields.BigIntField(primary_key=True)
    session: OneToOneRelation["ConcertSession"] = fields.OneToOneField(
        "models.ConcertSession",
        related_name="stream_channel",
        on_delete=fields.CASCADE,
        description="연결된 공연 (1:1)",
    )

    # IVS 상세 설정
    type = fields.CharEnumField(
        ChannelType, default=ChannelType.STANDARD, description="채널 타입(STANDARD, BASIC 등)"
    )
    latency_mode = fields.CharEnumField(
        LatencyMode, default=LatencyMode.LOW, description="지연모드 (LOW, NORMAL)"
    )
    transcoding_preset = fields.CharEnumField(
        TranscodingPreset,
        null=True,
        description="Advanced 채널용 트랜스코딩 품질 프리셋 (HBD, CBD)",
    )
    is_private = fields.BooleanField(
        default=True, description="비공개 여부 (Playback 토큰 인증 필요)"
    )
    is_record = fields.BooleanField(default=False, description="방송 녹화 및 VOD  생성 여부")

    # 엔드포인트 정보
    channel_arn = fields.CharField(
        max_length=255, unique=True, description="AWS IVS 채널 고유 리소스 이름"
    )
    ingest_endpoint = fields.CharField(
        max_length=255, description="OBS(송출 장비)에 설정할 RTMP 서버 주소"
    )
    playback_url = fields.CharField(
        max_length=255, description="사용자 플레이어에서 재생할 .m3u8 주소"
    )
    stream_key_encrypted = fields.TextField(description="Fernet으로 암호화된 스트림 키 (송출 권한)")

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "stream_channels"

    def __str__(self) -> str:
        return f"session_id={self.session.id} (id={self.id})"

    # 스트림 키를 대칭키 방식으로 암호화해서 DB에 저장
    def set_stream_key(self, plain_key: str) -> None:
        f = Fernet(settings.STREAM_KEY_ENCRYPTION_KEY.encode())
        self.stream_key_encrypted = f.encrypt(plain_key.encode()).decode()

    # 암호화된 스트림 키를 복호화해서 송출자에게 전달
    def get_stream_key(self) -> str:
        f = Fernet(settings.STREAM_KEY_ENCRYPTION_KEY.encode())
        return f.decrypt(self.stream_key_encrypted.encode()).decode()


class StreamSession(models.Model):
    """
    실제 방송 송출 이력 (session) 테이블
    - 한 공연(Concert) 안에서 방송이 켜지고 꺼질 때마다 기록 생성 (1:N)
    - 방송 사고나 재시작으로 인한 스트린 고유 ID(stream_id) 변화 추적
    """

    id = fields.BigIntField(primary_key=True)
    session: ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="stream_sessions", description="연결된 공연 회차 참조"
    )

    stream_id = fields.CharField(
        max_length=255, unique=True, description="AWS IVS에서 발급한 해당 방송 세션의 고유 ID"
    )
    started_at = fields.DatetimeField(description="실제 송출 시작 시각")
    ended_at = fields.DatetimeField(null=True, description="송출 종료 시각")
    peak_viewers = fields.IntField(default=0, description="해당 세션의 최대 동시 시청자 수")

    class Meta:
        table = "stream_sessions"

    def __str__(self) -> str:
        return f"{self.stream_id} (id={self.id})"


class StreamVod(models.Model):
    """
    방송 종료 후 생성된 VOD(다시보기) 관리 테이블
    - 방송 세션이 종료된 후 S3에 저장된 영상 파일 정보 (1:N)
    - 하나의 공연에 대해 여러 개의 영상(멀티캠, 파트별 녹화 기능)이 존재할 수 있음
    """

    id = fields.BigIntField(primary_key=True)
    session: ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="vods", description="연결된 공연 회차 참조"
    )

    s3_bucket = fields.CharField(max_length=100, description="저장 당시 S3 버킷 이름")
    s3_key_prefix = fields.CharField(max_length=255, description="S3 내 저장 폴더 경로")

    vod_url = fields.CharField(max_length=255, description="시청자용 재생 URL (CloudFront 주소 등)")
    file_name = fields.CharField(
        max_length=150, default="master.m3u8", description="메인 인덱스 파일 이름"
    )

    processing_status = fields.CharEnumField(
        VodStatus,
        max_length=20,
        default="PENDING",
        description="처리 상태: PENDING(대기), COMPLETED(완료), FAILED(실패)",
    )

    created_at = fields.DatetimeField(auto_now_add=True, description="VOD 생성/등록 시각")

    class Meta:
        table = "stream_vods"

    def __str__(self) -> str:
        return f"session_id={self.session.id} (id={self.id})"

    @property
    def full_s3_path(self) -> str:
        return f"{self.s3_bucket}/{self.s3_key_prefix}/{self.file_name}"
