from enum import Enum

from tortoise import fields, models

from app.domains.artists.models import Artist


class CategoryType(str, Enum):
    KPOP = "K-POP"
    TROT = "TROT"
    MUSICAL = "MUSICAL"
    BAND = "BAND"
    FAN_MEETING = "FAN_MEETING"
    KOREA_TOUR = "KOREA_TOUR"


class StreamStatus(str, Enum):
    READY = "READY"
    LIVE = "LIVE"
    ENDED = "ENDED"


class VodStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ChannelType(str, Enum):
    STANDARD = "STANDARD"
    ADVANCED_SD = "ADVANCED_SD"
    ADVANCED_HD = "ADVANCED_HD"
    BASIC = "BASIC"


class LatencyMode(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"


class TranscodingPreset(str, Enum):
    HBD = "HBD"
    CBD = "CBD"


class Concert(models.Model):
    id = fields.IntField(pk=True)
    category = fields.CharEnumField(CategoryType)
    title = fields.CharField(max_length=100, null=True)
    thumbnail_url = fields.CharField(max_length=255, null=True)
    start_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "concerts"


class ConcertArtist(models.Model):
    id = fields.IntField(pk=True)
    concert: fields.ForeignKeyRelation["Concert"] = fields.ForeignKeyField(
        "models.Concert", related_name="concert_artists"
    )
    artist: fields.ForeignKeyRelation["Artist"] = fields.ForeignKeyField(
        "models.Artist", related_name="concerts"
    )
    is_main = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "concert_artists"
        unique_together = (("concert", "artist"),)


class StreamChannel(models.Model):
    id = fields.IntField(pk=True)
    concert: fields.OneToOneRelation["Concert"] = fields.OneToOneField(
        "models.Concert", related_name="stream_channel"
    )
    type = fields.CharEnumField(ChannelType, default=ChannelType.STANDARD)
    latency_mode = fields.CharEnumField(LatencyMode, default=LatencyMode.LOW)
    transcoding_preset = fields.CharEnumField(TranscodingPreset, null=True)
    is_private = fields.BooleanField(default=True)
    is_record = fields.BooleanField(default=False)
    channel_arn = fields.CharField(max_length=255, unique=True)
    ingest_endpoint = fields.CharField(max_length=255)
    playback_url = fields.CharField(max_length=255)
    stream_key_encrypted = fields.TextField()
    status = fields.CharField(max_length=20, default="READY")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "stream_channels"


class StreamSession(models.Model):
    id = fields.IntField(pk=True)
    concert: fields.ForeignKeyRelation["Concert"] = fields.ForeignKeyField(
        "models.Concert", related_name="sessions"
    )
    stream_id = fields.CharField(max_length=255, unique=True)
    started_at = fields.DatetimeField()
    ended_at = fields.DatetimeField(null=True)
    peak_viewers = fields.IntField(default=0)

    class Meta:
        table = "stream_sessions"


class StreamVod(models.Model):
    id = fields.IntField(pk=True)
    concert: fields.ForeignKeyRelation["Concert"] = fields.ForeignKeyField(
        "models.Concert", related_name="vods"
    )
    s3_bucket = fields.CharField(max_length=100)
    s3_key_prefix = fields.CharField(max_length=255)
    vod_url = fields.CharField(max_length=255)
    file_name = fields.CharField(max_length=150, default="master.m3u8")
    processing_status = fields.CharField(max_length=20, default="PENDING")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stream_vods"
