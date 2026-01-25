from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect
from tortoise.exceptions import IntegrityError

from app.core.config import KST, now_kst
from app.domains.artists.models import Artist
from app.domains.notifications.models import ConcertNoti, NotiKind, NotiStatus, UserNoti
from app.domains.notifications.service import (
    NotificationService,
    _build_content,
    _build_schedule,
    _normalize_start_at,
)
from app.domains.streams.models import CategoryType, Concert, ConcertSession, StreamStatus
from app.domains.users.models import ProviderChoice, User, UserCatFav


class _DummyQuery:
    def __init__(self, result):
        self._result = result

    def exclude(self, **kwargs):
        return self

    def prefetch_related(self, *args, **kwargs):
        return self

    def __await__(self):
        async def _run():
            return self._result

        return _run().__await__()


@pytest.mark.asyncio
async def test_normalize_start_at_handles_naive_and_aware() -> None:
    naive = datetime(2024, 1, 1, 10, 0)
    normalized = _normalize_start_at(naive)
    assert normalized.tzinfo == KST
    assert normalized.hour == 10

    aware = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
    normalized = _normalize_start_at(aware)
    assert normalized.tzinfo == KST
    assert normalized.hour == 10


@pytest.mark.asyncio
async def test_build_schedule_and_content_variants() -> None:
    concert = await Concert.create(title="Notice", category=CategoryType.KPOP)
    start_at = datetime(2024, 1, 2, 8, 0)
    session = await ConcertSession.create(concert=concert, session_name="Session A", start_at=start_at)
    await session.fetch_related("concert")

    schedule = _build_schedule(start_at)
    assert schedule[NotiKind.START].hour == 8
    assert schedule[NotiKind.HOUR_1].hour == 7
    assert schedule[NotiKind.MIN_30].minute == 30
    assert schedule[NotiKind.DAY_BEFORE].date().isoformat() == "2024-01-01"
    assert schedule[NotiKind.DAY_BEFORE].hour == 0

    expected = {
        NotiKind.DAY_BEFORE: "내일 라이브 시작 예정",
        NotiKind.HOUR_1: "라이브 시작 1시간 전",
        NotiKind.MIN_30: "라이브 시작 30분 전",
        NotiKind.START: "라이브 시작",
    }
    for kind, prefix in expected.items():
        title, message = _build_content(session, kind)
        assert concert.title in title
        assert prefix in message
        assert session.session_name in message


@pytest.mark.asyncio
async def test_schedule_session_notifications_creates_and_skips_duplicates() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_notice",
        nickname="notice_user",
    )
    concert = await Concert.create(title="Schedule", category=CategoryType.KPOP)
    session = await ConcertSession.create(concert=concert, session_name="One", start_at=now_kst())

    service = NotificationService()
    with patch.object(service, "_resolve_target_user_ids", new=AsyncMock(return_value=[user.id])):
        created = await service.schedule_session_notifications(session.id, session=session)
        assert created == 4
        created_again = await service.schedule_session_notifications(session.id, session=session)
        assert created_again == 0

    assert await ConcertNoti.filter(session_id=session.id).count() == 4


@pytest.mark.asyncio
async def test_schedule_session_notifications_handles_integrity_error() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_integrity",
        nickname="integrity_user",
    )
    concert = await Concert.create(title="Integrity", category=CategoryType.KPOP)
    session = await ConcertSession.create(concert=concert, session_name="Two", start_at=now_kst())

    service = NotificationService()
    with (
        patch.object(service, "_resolve_target_user_ids", new=AsyncMock(return_value=[user.id])),
        patch(
            "app.domains.notifications.service.ConcertNoti.bulk_create",
            new=AsyncMock(side_effect=IntegrityError("dup")),
        ),
    ):
        created = await service.schedule_session_notifications(session.id, session=session)
        assert created == 4

    assert await ConcertNoti.filter(session_id=session.id).count() == 4


@pytest.mark.asyncio
async def test_schedule_session_notifications_returns_zero_for_ended() -> None:
    concert = await Concert.create(title="Ended", category=CategoryType.KPOP)
    session = await ConcertSession.create(
        concert=concert,
        session_name="Ended",
        start_at=now_kst(),
        status=StreamStatus.ENDED,
    )
    service = NotificationService()
    created = await service.schedule_session_notifications(session.id)
    assert created == 0


@pytest.mark.asyncio
async def test_schedule_session_notifications_returns_zero_for_no_targets() -> None:
    concert = await Concert.create(title="NoTarget", category=CategoryType.KPOP)
    session = await ConcertSession.create(concert=concert, session_name="NoTarget", start_at=now_kst())

    service = NotificationService()
    with patch.object(service, "_resolve_target_user_ids", new=AsyncMock(return_value=[])):
        created = await service.schedule_session_notifications(session.id, session=session)
    assert created == 0


@pytest.mark.asyncio
async def test_schedule_upcoming_sessions_filters_and_calls() -> None:
    base_time = now_kst()
    concert = await Concert.create(title="Upcoming", category=CategoryType.KPOP)
    ready_session = await ConcertSession.create(
        concert=concert,
        session_name="Ready",
        start_at=base_time + timedelta(hours=1),
    )
    await ConcertSession.create(
        concert=concert,
        session_name="Ended",
        start_at=base_time + timedelta(hours=1),
        status=StreamStatus.ENDED,
    )

    service = NotificationService()
    dummy_query = _DummyQuery([ready_session])
    with (
        patch("app.domains.notifications.service.ConcertSession.filter", return_value=dummy_query),
        patch.object(service, "schedule_session_notifications", new=AsyncMock(return_value=1)) as mock_sched,
    ):
        total = await service.schedule_upcoming_sessions(hours_ahead=2)

    assert total == 1
    assert mock_sched.await_count == 1
    call_args = mock_sched.await_args
    assert call_args.args[0] == ready_session.id
    assert call_args.kwargs["session"].id == ready_session.id


@pytest.mark.asyncio
async def test_deliver_concert_notification_publishes() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_publish",
        nickname="publish_user",
    )
    concert = await Concert.create(title="Deliver", category=CategoryType.KPOP)
    session = await ConcertSession.create(concert=concert, session_name="Delivery", start_at=now_kst())
    noti = await ConcertNoti.create(
        user=user,
        session=session,
        kind=NotiKind.START,
        title="start",
        message="msg",
        send_at=now_kst(),
        status=NotiStatus.PENDING,
    )

    service = NotificationService()
    with patch("app.domains.notifications.service.notification_manager.publish", new=AsyncMock()) as mock_pub:
        ok = await service.deliver_concert_notification(noti)

    assert ok is True
    mock_pub.assert_awaited_once()
    args = mock_pub.call_args.args
    assert args[0] == str(user.id)
    assert "notification" in args[1]


@pytest.mark.asyncio
async def test_handle_ws_connection_disconnects() -> None:
    service = NotificationService()
    ws = AsyncMock()
    ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    with (
        patch("app.domains.notifications.service.notification_manager.ensure_subscriber", new=AsyncMock()),
        patch("app.domains.notifications.service.notification_manager.connect", new=AsyncMock()),
        patch("app.domains.notifications.service.notification_manager.disconnect", new=AsyncMock()) as mock_disconnect,
    ):
        await service.handle_ws_connection(ws, user_id=1)

    mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_ws_connection_runtime_error_closes() -> None:
    service = NotificationService()
    ws = AsyncMock()

    with (
        patch("app.domains.notifications.service.notification_manager.ensure_subscriber", new=AsyncMock()),
        patch(
            "app.domains.notifications.service.notification_manager.connect",
            new=AsyncMock(side_effect=RuntimeError("busy")),
        ),
        patch("app.domains.notifications.service.notification_manager.disconnect", new=AsyncMock()) as mock_disconnect,
    ):
        await service.handle_ws_connection(ws, user_id=1)

    ws.close.assert_awaited_once_with(code=1008)
    mock_disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_target_user_ids_combines_filters() -> None:
    concert = await Concert.create(title="Filters", category=CategoryType.KPOP)
    session = await ConcertSession.create(concert=concert, session_name="Mix", start_at=now_kst())

    artist = await Artist.create(stage_name="Artist A")
    await session.lineup.add(artist)

    user1 = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_filter_1",
        nickname="filter1",
    )
    await UserNoti.create(user=user1, artist_noti=True, live_noti=True, marketing_noti=False)
    await user1.followed_artists.add(artist)

    user2 = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_filter_2",
        nickname="filter2",
    )
    await UserNoti.create(user=user2, artist_noti=False, live_noti=True, marketing_noti=False)
    await UserCatFav.create(user=user2, category=CategoryType.KPOP)

    service = NotificationService()
    user_ids = await service._resolve_target_user_ids(session)

    assert set(user_ids) == {user1.id, user2.id}
