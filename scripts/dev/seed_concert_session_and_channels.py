import asyncio
from datetime import datetime, timedelta

from tortoise import Tortoise

from app.core.config import settings
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.streams.models import (
    AccessLevel,
    ChannelType,
    ConcertSession,
    LatencyMode,
    StreamChannel,
    StreamStatus,
)


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    # 퍼블릭 엑세스 ============================================================
    await ConcertSession.get_or_create(
        id=1,
        defaults={
            "session_name": "mock_public",
            "status": StreamStatus.READY,
            "access_level": AccessLevel.PUBLIC,
            "is_test": False,
            "start_at": datetime.now() + timedelta(hours=5),
            "end_at": datetime.now() + timedelta(hours=8),
            "concert_id": 2,
        },
    )
    await StreamChannel.get_or_create(
        id=1,
        defaults={
            "type": ChannelType.STANDARD,
            "latency_mode": LatencyMode.LOW,
            "is_private": False,
            "channel_arn": "arn:aws:ivs:ap-northeast-2:123456789012:channel/mock-channel-1",
            "ingest_endpoint": "rtmps://mock.ingest.endpoint/app/",
            "stream_key_encrypted": "mock_encrypted_stream_key",
            "playback_url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
            "session_id": 1,
        },
    )

    # 특정 유저 엑세스 ============================================================
    await ConcertSession.get_or_create(
        id=2,
        defaults={
            "session_name": "mock_specific",
            "status": StreamStatus.READY,
            "access_level": AccessLevel.SPECIFIC,
            "is_test": False,
            "start_at": datetime.now() + timedelta(hours=5),
            "end_at": datetime.now() + timedelta(hours=8),
            "concert_id": 2,
        },
    )
    await StreamChannel.get_or_create(
        id=2,
        defaults={
            "type": ChannelType.STANDARD,
            "latency_mode": LatencyMode.LOW,
            "is_private": True,
            "channel_arn": "arn:aws:ivs:ap-northeast-2:123456789012:channel/mock-channel-2",
            "ingest_endpoint": "rtmps://mock.ingest.endpoint/app/",
            "stream_key_encrypted": "mock_encrypted_stream_key",
            "playback_url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
            "session_id": 2,
        },
    )

    # 어드민 온리 - 테스트 중 ============================================================
    await ConcertSession.get_or_create(
        id=3,
        defaults={
            "session_name": "mock_admin_only",
            "status": StreamStatus.READY,
            "access_level": AccessLevel.ADMIN_ONLY,
            "is_test": True,
            "start_at": datetime.now() + timedelta(hours=5),
            "end_at": datetime.now() + timedelta(hours=8),
            "concert_id": 2,
        },
    )

    await StreamChannel.get_or_create(
        id=3,
        defaults={
            "type": ChannelType.STANDARD,
            "latency_mode": LatencyMode.LOW,
            "is_private": True,
            "channel_arn": "arn:aws:ivs:ap-northeast-2:123456789012:channel/mock-channel-3",
            "ingest_endpoint": "rtmps://mock.ingest.endpoint/app/",
            "stream_key_encrypted": "mock_encrypted_stream_key",
            "playback_url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
            "session_id": 3,
        },
    )

    await Tortoise.close_connections()

    print(f"[{settings.MODE}] 개발용 콘서트 세션 + 스트림 채널 생성 완료")


if __name__ == "__main__":
    asyncio.run(main())
