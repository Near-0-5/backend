from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.streams.models import AccessLevel, Concert, StreamChannel
from app.domains.streams.schemas import ConcertCreateRequest
from app.domains.streams.service import StreamService
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_create_concert_and_channel_admin_success(monkeypatch):
    """관리자는 공연, 스트림 채널 생성 가능"""
    admin = MagicMock(spec=User)
    admin.is_superuser = True

    # 권한 체크는 통과만 시킴
    monkeypatch.setattr(
        "app.domains.streams.permissions.StreamPermission.must_be_admin",
        MagicMock(),
    )

    # Concert 생성 mock
    concert = MagicMock(spec=Concert)
    concert.id = 1
    concert.access_level = AccessLevel.PUBLIC

    monkeypatch.setattr(
        "app.domains.streams.service.Concert.create",
        AsyncMock(return_value=concert),
    )

    # StreamChannel 생성 mock
    channel = MagicMock(spec=StreamChannel)
    monkeypatch.setattr(
        "app.domains.streams.service.StreamChannel.create",
        AsyncMock(return_value=channel),
    )

    # IVS 채널 생성 응답 mock
    ivs_client = MagicMock()
    ivs_client.create_channel.return_value = {
        "channel": {
            "arn": "arn:test",
            "ingestEndpoint": "ingest",
            "playbackUrl": "playback",
        },
        "streamKey": {"value": "secret"},
    }

    # 스트림 키 저장 및 DB 저장 mock
    channel.set_stream_key = MagicMock()
    channel.save = AsyncMock()

    playback_provider = MagicMock()

    service = StreamService(ivs_client, playback_provider)

    # 요청 데이터 mock
    data = MagicMock(spec=ConcertCreateRequest)
    data.model_dump.return_value = {
        "title": "test",
        "access_level": AccessLevel.PUBLIC,
    }
    data.artist_ids = []
    data.channel_config = MagicMock()
    data.channel_config.latency_mode.value = "LOW"
    data.channel_config.channel_type.value = "STANDARD"

    result = await service.create_concert_and_channel(data=data, user=admin)

    # 생성된 Concert 반환
    assert result is concert

    # IVS 채널 생성 호출 여부 확인
    ivs_client.create_channel.assert_called_once()


@pytest.mark.asyncio
async def test_public_channel_does_not_add_playback_token(monkeypatch):
    """PUBLIC은 playback token 없어도 URL 줌"""
    user = MagicMock(spec=User)
    user.id = 1
    user.is_superuser = False

    channel = MagicMock(spec=StreamChannel)
    channel.is_private = False
    channel.playback_url = "https://example.m3u8"
    channel.channel_arn = "arn:test"

    concert = MagicMock(spec=Concert)
    concert.id = 10
    concert.stream_channel = channel
    concert.access_level = AccessLevel.PUBLIC

    # Concert 조회 + stream_channel preload mock
    fake_qs = MagicMock()
    fake_qs.prefetch_related = AsyncMock(return_value=concert)

    monkeypatch.setattr(
        "app.domains.streams.service.Concert.get",
        MagicMock(return_value=fake_qs),
    )

    playback_provider = MagicMock()
    playback_provider.sign_internal_tokens.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
    }

    service = StreamService(MagicMock(), playback_provider)

    result = await service.get_viewing_credentials(concert_id=10, user=user)

    # playback URL 확인
    assert result["playback_url"] == "https://example.m3u8"
    playback_provider.sign_playback_token.assert_not_called()


@pytest.mark.asyncio
async def test_private_channel_adds_playback_token(monkeypatch):
    """SPECIFIC은 playback token이 URL 뒤에 붙음"""
    user = MagicMock(spec=User)
    user.id = 1
    user.is_superuser = False

    channel = MagicMock(spec=StreamChannel)
    channel.is_private = True
    channel.playback_url = "https://example.m3u8"
    channel.channel_arn = "arn:test"

    concert = MagicMock(spec=Concert)
    concert.id = 10
    concert.stream_channel = channel
    concert.access_level = AccessLevel.PUBLIC

    fake_qs = MagicMock()
    fake_qs.prefetch_related = AsyncMock(return_value=concert)

    monkeypatch.setattr(
        "app.domains.streams.service.Concert.get",
        MagicMock(return_value=fake_qs),
    )

    playback_provider = MagicMock()
    playback_provider.sign_playback_token.return_value = "signed-token"
    playback_provider.sign_internal_tokens.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
    }

    service = StreamService(MagicMock(), playback_provider)

    result = await service.get_viewing_credentials(concert_id=10, user=user)

    # # playback token이 URL 뒤에 붙었나 확인
    assert "?token=signed-token" in result["playback_url"]
    playback_provider.sign_playback_token.assert_called_once()
