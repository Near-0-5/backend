from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.domains.concerts.models import CategoryType, Concert
from app.domains.streams.admin.schemas import SessionUpdateRequest
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.models import (
    AccessLevel,
    ChannelType,
    ConcertSession,
    LatencyMode,
    StreamChannel,
    StreamStatus,
)
from app.domains.users.models import ProviderChoice, User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


@pytest.fixture
def admin_service():
    return StreamAdminService(
        ivs_client=IVSClient(),
        playback_provider=IVSPlaybackProvider(),
    )


@pytest.fixture
async def admin_user():
    return await User.create(
        id=1,
        provider=ProviderChoice.KAKAO,
        provider_id="test-admin-1",
        nickname="admin",
        is_superuser=True,
    )


@pytest.fixture
async def concert():
    return await Concert.create(
        title="테스트 콘서트",
        category=CategoryType.KPOP,
        description="test",
    )


@pytest.fixture
async def session_with_channel(concert):
    session = await ConcertSession.create(
        concert=concert,
        session_name="1회차",
        start_at=datetime.now() + timedelta(hours=1),
        status=StreamStatus.READY,
        access_level=AccessLevel.PUBLIC,
    )

    await StreamChannel.create(
        session=session,
        channel_arn="arn:ivs:test:channel/1",
        ingest_endpoint="rtmp://test",
        playback_url="https://playback.m3u8",
        type=ChannelType.STANDARD,
        latency_mode=LatencyMode.LOW,
        is_private=False,
        stream_key_encrypted="dummy",
    )
    return session


@pytest.mark.asyncio
async def test_list_sessions_admin_live_overrides_db(
    admin_service, admin_user, session_with_channel, monkeypatch
):
    service = admin_service

    def fake_list_live_streams():
        return [{"channelArn": "arn:ivs:test:channel/1"}]

    monkeypatch.setattr(
        service.ivs_client,
        "list_live_streams",
        fake_list_live_streams,
    )

    results, next_cursor = await service.list_sessions_admin(admin_user)

    assert next_cursor is None
    assert len(results) == 1
    assert results[0].status == StreamStatus.LIVE


@pytest.mark.asyncio
async def test_list_sessions_admin_aws_failure_fallback(
    admin_service, admin_user, session_with_channel, monkeypatch
):
    service = admin_service

    def raise_error():
        raise Exception("AWS down")

    monkeypatch.setattr(
        service.ivs_client,
        "list_live_streams",
        raise_error,
    )

    results, _ = await service.list_sessions_admin(admin_user)

    assert results[0].status == StreamStatus.READY


@pytest.mark.asyncio
async def test_get_session_admin_detail_success(admin_service, admin_user, session_with_channel):
    service = admin_service

    res = await service.get_session_admin_detail(
        session_with_channel.id,
        admin_user,
    )

    assert res.id == session_with_channel.id
    assert res.channel is not None
    assert res.channel.arn == "arn:ivs:test:channel/1"


@pytest.mark.asyncio
async def test_get_session_admin_detail_not_found(admin_service, admin_user):
    service = admin_service

    with pytest.raises(HTTPException) as exc:
        await service.get_session_admin_detail(999, admin_user)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_session_updates_db_and_calls_aws(
    admin_service, admin_user, session_with_channel, monkeypatch
):
    service = admin_service
    called = {}

    def fake_update_channel(**kwargs):
        called["yes"] = True
        return {}

    monkeypatch.setattr(
        service.ivs_client,
        "update_channel",
        fake_update_channel,
    )

    data = SessionUpdateRequest(
        session_name="수정됨",
        access_level=AccessLevel.ADMIN_ONLY,
        channel_config={"latencyMode": LatencyMode.NORMAL},
    )

    res = await service.update_session_infrastructure(
        session_with_channel.id,
        data,
        admin_user,
    )

    assert called.get("yes") is True
    assert res.session_name == "수정됨"
    assert res.access_level == AccessLevel.ADMIN_ONLY


@pytest.mark.asyncio
async def test_sync_session_status_to_live(admin_service, session_with_channel, monkeypatch):
    service = admin_service

    monkeypatch.setattr(
        service.ivs_client,
        "get_stream_health",
        lambda arn: {"stream": {"state": "LIVE"}},
    )

    channel = await session_with_channel.stream_channel.first()

    status, res = await service._sync_session_status_with_aws(
        session_with_channel,
        channel,
    )

    assert status == StreamStatus.LIVE
    assert res is not None


@pytest.mark.asyncio
async def test_sync_does_not_override_ended(admin_service, session_with_channel, monkeypatch):
    service = admin_service
    session_with_channel.status = StreamStatus.ENDED
    await session_with_channel.save()

    monkeypatch.setattr(
        service.ivs_client,
        "get_stream_health",
        lambda arn: {"stream": {}},
    )

    channel = await session_with_channel.stream_channel.first()

    status, _ = await service._sync_session_status_with_aws(
        session_with_channel,
        channel,
    )

    assert status == StreamStatus.ENDED
