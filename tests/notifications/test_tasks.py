from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import now_kst
from app.domains.concerts.models import Concert
from app.domains.notifications.models import ConcertNoti, NotiKind, NotiStatus
from app.domains.notifications.tasks import _dispatch_due_notifications
from app.domains.streams.models import ConcertSession, StreamStatus
from app.domains.users.models import ProviderChoice, User


@pytest.mark.asyncio
async def test_dispatch_due_notifications_sends_ready_and_live():
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_dispatch",
        nickname="dispatch_user",
    )
    concert = await Concert.create(title="Dispatch Test")

    ready_session = await ConcertSession.create(
        concert=concert,
        session_name="ready",
        start_at=now_kst(),
    )
    live_session = await ConcertSession.create(
        concert=concert,
        session_name="live",
        start_at=now_kst(),
        status=StreamStatus.LIVE,
    )

    ready_noti = await ConcertNoti.create(
        user=user,
        session=ready_session,
        kind=NotiKind.HOUR_1,
        title="ready",
        message="ready",
        send_at=now_kst() - timedelta(minutes=1),
    )
    live_noti = await ConcertNoti.create(
        user=user,
        session=live_session,
        kind=NotiKind.START,
        title="live",
        message="live",
        send_at=now_kst() + timedelta(minutes=30),
    )

    with patch(
        "app.domains.notifications.service.notification_manager.publish",
        new=AsyncMock(),
    ) as mock_publish:
        sent = await _dispatch_due_notifications(batch_size=10)
        assert sent == 2
        assert mock_publish.await_count == 2

    refreshed_ready = await ConcertNoti.get(id=ready_noti.id)
    refreshed_live = await ConcertNoti.get(id=live_noti.id)

    assert refreshed_ready.status == NotiStatus.SENT
    assert refreshed_ready.sent_at is not None
    assert refreshed_live.status == NotiStatus.SENT
    assert refreshed_live.sent_at is not None
