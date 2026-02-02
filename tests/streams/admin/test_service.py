from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.config import now_kst
from app.domains.concerts.models import CategoryType, Concert
from app.domains.streams.admin.schemas import (
    ChannelConfig,
    SessionCreateRequest,
    StreamWebhookPayload,
)
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.models import (
    AccessLevel,
    ChannelType,
    ConcertSession,
    LatencyMode,
    StreamChannel,
    StreamSession,
    StreamStatus,
)
from app.domains.users.models import ProviderChoice, User


@pytest.fixture
def fake_ivs_client(mocker):
    client = mocker.Mock()

    client.create_channel.return_value = {
        "channel": {
            "arn": "arn:ivs:test:channel/1",
            "ingestEndpoint": "rtmps://test.ingest",
            "playbackUrl": "https://test.playback.m3u8",
        },
        "streamKey": {"value": "raw-stream-key"},
    }

    client.get_stream_health.return_value = None
    client.list_all_stream_keys.return_value = []
    client.create_stream_key.return_value = {"streamKey": {"value": "new-stream-key"}}

    return client


@pytest.fixture
def fake_playback_provider(mocker):
    provider = mocker.Mock()
    provider.sign_playback_token.return_value = "signed-token"
    return provider


@pytest.fixture
def admin_service(fake_ivs_client, fake_playback_provider):
    return StreamAdminService(fake_ivs_client, fake_playback_provider)


@pytest.fixture
async def admin_user():
    return await User.create(
        email="admin@test.com",
        is_admin=True,
        provider=ProviderChoice.KAKAO,
        provider_id="admin-test-id",
        nickname="admin",
        is_superuser=True,
    )


@pytest.fixture
async def concert():
    return await Concert.create(
        title="테스트 콘서트", category=CategoryType.KPOP, thumbnail_url="https://thumb.test"
    )


@pytest.fixture(autouse=True)
def bypass_stream_key_crypto(monkeypatch):
    monkeypatch.setattr(
        StreamChannel,
        "set_stream_key",
        lambda self, raw: setattr(self, "stream_key_encrypted", "encrypted"),
    )
    monkeypatch.setattr(
        StreamChannel,
        "get_stream_key",
        lambda self: "raw-stream-key",
    )


@pytest.mark.asyncio
async def test_create_session_with_infrastructure(admin_service, admin_user, concert):
    req = SessionCreateRequest(
        session_name="라이브 세션",
        start_at=now_kst() + timedelta(hours=1),
        access_level=AccessLevel.PUBLIC,
        channel_config=ChannelConfig(
            latency_mode=LatencyMode.LOW,
            type=ChannelType.STANDARD,
        ),
    )

    res = await admin_service.create_session_with_infrastructure(concert.id, req, admin_user)

    assert res.session_name == "라이브 세션"
    assert res.status == StreamStatus.READY
    assert res.channel is not None
    assert res.channel.arn == "arn:ivs:test:channel/1"
    assert res.stream_key == "raw-stream-key"


@pytest.mark.asyncio
async def test_list_sessions_admin(admin_service, admin_user, concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="목록 테스트",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.READY,
    )

    res = await admin_service.list_sessions_admin(admin_user)

    assert res.next_cursor is None
    assert len(res.items) == 1
    assert res.items[0].id == session.id
    assert res.items[0].status == StreamStatus.READY


@pytest.mark.asyncio
async def test_list_sessions_admin_live_overrides_db(
    admin_service, admin_user, concert, fake_ivs_client
):
    session = await ConcertSession.create(
        concert=concert,
        session_name="LIVE 세션",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.READY,
    )
    await session.fetch_related("concert")
    await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmps://test",
        playback_url="https://test.m3u8",
        latency_mode=LatencyMode.LOW,
        type=ChannelType.STANDARD,
        is_private=False,
        stream_key_encrypted="encrypted",
    )

    fake_ivs_client.get_stream_health.return_value = {"stream": {"health": "LIVE"}}

    await admin_service.get_stream_ingest_info(session.id, admin_user)

    await session.refresh_from_db()
    assert session.status == StreamStatus.LIVE


@pytest.mark.asyncio
async def test_get_session_admin_detail(admin_service, admin_user, concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="상세 조회",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.READY,
    )

    channel = await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmps://test",
        playback_url="https://test.m3u8",
        latency_mode=LatencyMode.LOW,
        type=ChannelType.STANDARD,
        is_private=False,
        stream_key_encrypted="encrypted",
    )

    res = await admin_service.get_session_admin_detail(session.id, admin_user)

    assert res.id == session.id
    assert res.channel.arn == channel.channel_arn


@pytest.mark.asyncio
async def test_stop_stream_session(admin_service, admin_user, concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="종료 테스트",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.LIVE,
    )

    await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmps://test",
        playback_url="https://test.m3u8",
        latency_mode=LatencyMode.LOW,
        type=ChannelType.STANDARD,
        is_private=False,
        stream_key_encrypted="encrypted",
    )

    await admin_service.stop_stream_session(session.id, admin_user)

    await session.refresh_from_db()
    assert session.status == StreamStatus.ENDED


@pytest.mark.asyncio
async def test_handle_ivs_webhook_stream_start(admin_service, concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="웹훅 시작",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.READY,
    )

    channel = await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmps://test",
        playback_url="https://test.m3u8",
        latency_mode=LatencyMode.LOW,
        type=ChannelType.STANDARD,
        is_private=False,
        stream_key_encrypted="encrypted",
    )

    payload = {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "IVS Stream State Change",
        "source": "aws.ivs",
        "account": "123456789012",
        "time": "2024-01-01T00:00:00Z",
        "region": "ap-northeast-2",
        "resources": [channel.channel_arn],
        "detail": {
            "event_name": "Stream Start",
            "channel_arn": channel.channel_arn,
            "stream_id": "stream-1",
        },
    }

    await admin_service.handle_ivs_webhook(StreamWebhookPayload.model_validate(payload))

    await session.refresh_from_db()
    assert session.status == StreamStatus.LIVE

    hist = await StreamSession.get_or_none(stream_id="stream-1")
    assert hist is not None


@pytest.mark.asyncio
async def test_rotate_stream_key(admin_service, admin_user, concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="키 로테이션",
        start_at=now_kst(),
        access_level=AccessLevel.PUBLIC,
        status=StreamStatus.READY,
    )

    await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmps://test",
        playback_url="https://test.m3u8",
        latency_mode=LatencyMode.LOW,
        type=ChannelType.STANDARD,
        is_private=False,
        stream_key_encrypted="encrypted",
    )

    new_key = await admin_service.rotate_stream_key(session.id, admin_user)

    assert new_key == "new-stream-key"


@pytest.mark.asyncio
async def test_cleanup_on_failure_calls_delete_channel_and_session(admin_service):
    # ivs_client.delete_channel 예외 처리
    admin_service.ivs_client.delete_channel = Mock(side_effect=Exception("AWS fail"))

    with patch("app.domains.streams.admin.service.ConcertSession.filter") as mock_filter:
        mock_filter.return_value.delete = AsyncMock()
        await admin_service._cleanup_on_failure(
            session_id=1, channel_arn="arn:aws:ivs:1234:channel/abcd"
        )
        admin_service.ivs_client.delete_channel.assert_called_once_with(
            "arn:aws:ivs:1234:channel/abcd"
        )
        mock_filter.return_value.delete.assert_awaited()


@pytest.mark.asyncio
async def test_rotate_stream_key_creates_new_key_and_updates_db(admin_service):
    channel = MagicMock(spec=StreamChannel)
    channel.channel_arn = "arn:aws:ivs:1234:channel/abcd"
    channel.set_stream_key = MagicMock()
    channel.save = AsyncMock()
    session = MagicMock(spec=ConcertSession)
    session.stream_channel = channel

    with patch.object(admin_service, "_get_session_with_channel_or_raise", return_value=session):
        new_key = await admin_service.rotate_stream_key(1, MagicMock(spec=User))
        assert new_key == "new-stream-key"
        channel.set_stream_key.assert_called_with("new-stream-key")
        channel.save.assert_awaited_with(update_fields=["stream_key_encrypted"])


@pytest.mark.asyncio
async def test_handle_ivs_webhook_stream_end_updates_status(admin_service):
    from app.domains.streams.models import StreamSession

    # Mock session과 stream_hist
    session = MagicMock(spec=ConcertSession)
    session.status = StreamStatus.LIVE
    session.save = AsyncMock()
    session.stream_channel = MagicMock()
    session.stream_channel.session = session

    stream_hist = MagicMock(spec=StreamSession)
    stream_hist.save = AsyncMock()

    payload = SimpleNamespace(
        detail=SimpleNamespace(
            event_name="Stream End", channel_arn="arn:channel", stream_id="stream123"
        )
    )

    mock_channel = AsyncMock()
    mock_channel.prefetch_related.return_value = mock_channel
    mock_channel.session = session

    with (
        patch(
            "app.domains.streams.admin.service.StreamChannel.get_or_none", return_value=mock_channel
        ),
        patch(
            "app.domains.streams.admin.service.StreamSession.get_or_none",
            new_callable=AsyncMock,
            return_value=stream_hist,
        ),
    ):
        await admin_service.handle_ivs_webhook(payload)

        assert session.status == StreamStatus.ENDED
        stream_hist.save.assert_awaited_with(update_fields=["ended_at"])


@pytest.mark.asyncio
async def test_get_stream_ingest_info_calls_playback_provider(admin_service):
    # 채널 mock
    channel = MagicMock(spec=StreamChannel)
    channel.channel_arn = "arn:aws:ivs:1234:channel/abcd"
    channel.is_private = True
    channel.playback_url = "https://playback.test"
    channel.ingest_endpoint = "rtmps://ingest.test"
    channel.get_stream_key.return_value = "streamkey123"
    channel.save = AsyncMock()

    # 콘서트 mock
    concert = MagicMock()
    concert.title = "테스트 콘서트"

    # 세션 mock
    session = MagicMock(spec=ConcertSession)
    session.id = 1
    session.status = StreamStatus.READY
    session.session_name = "테스트 세션"
    session.concert = concert
    session.stream_channel = channel

    # user mock
    mock_user = MagicMock(spec=User)
    mock_user.id = 123

    with patch.object(admin_service, "_get_session_with_channel_or_raise", return_value=session):
        response = await admin_service.get_stream_ingest_info(1, mock_user)

        assert response.playback_token == "signed-token"
        admin_service.playback_provider.sign_playback_token.assert_called_once()
