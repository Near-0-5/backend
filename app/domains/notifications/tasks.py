import asyncio
import logging

from tortoise import Tortoise

from app.core.config import now_kst
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.notifications.models import ConcertNoti, NotiKind, NotiStatus
from app.domains.notifications.service import notification_service
from app.domains.streams.models import StreamStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger("app.notifications")


async def _run_with_db(coro):
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        return await coro
    finally:
        await Tortoise.close_connections()


@celery_app.task(name="app.domains.notifications.tasks.schedule_session_notifications")
def schedule_session_notifications(session_id: int) -> int:
    return asyncio.run(_run_with_db(notification_service.schedule_session_notifications(session_id)))


@celery_app.task(name="app.domains.notifications.tasks.schedule_upcoming_session_notifications")
def schedule_upcoming_session_notifications(hours_ahead: int = 24) -> int:
    return asyncio.run(
        _run_with_db(notification_service.schedule_upcoming_sessions(hours_ahead=hours_ahead))
    )


@celery_app.task(name="app.domains.notifications.tasks.dispatch_due_notifications")
def dispatch_due_notifications(batch_size: int = 200) -> int:
    return asyncio.run(_run_with_db(_dispatch_due_notifications(batch_size)))


async def _dispatch_due_notifications(batch_size: int) -> int:
    now = now_kst()
    total = 0
    due_query = (
        ConcertNoti.filter(
            status=NotiStatus.PENDING,
            send_at__lte=now,
            session__status=StreamStatus.READY,
        )
        .exclude(kind=NotiKind.START)
        .order_by("send_at")
    )
    total += await _dispatch_notifications(due_query, now, batch_size)

    start_query = (
        ConcertNoti.filter(
            status=NotiStatus.PENDING,
            kind=NotiKind.START,
            session__status=StreamStatus.LIVE,
        )
        .order_by("send_at")
    )
    total += await _dispatch_notifications(start_query, now, batch_size)

    return total

async def _dispatch_notifications(query, now, batch_size: int) -> int:
    items = await query.limit(batch_size)
    sent = 0

    for noti in items:
        claimed = await ConcertNoti.filter(
            id=noti.id, status=NotiStatus.PENDING
        ).update(status=NotiStatus.PROCESSING, updated_at=now)
        if not claimed:
            continue

        try:
            ok = await notification_service.deliver_concert_notification(noti)
        except Exception:
            logger.exception("Failed to deliver notification id=%s", noti.id)
            ok = False

        if ok:
            await ConcertNoti.filter(id=noti.id).update(
                status=NotiStatus.SENT, sent_at=now, updated_at=now
            )
            sent += 1
        else:
            await ConcertNoti.filter(id=noti.id).update(
                status=NotiStatus.FAILED, updated_at=now
            )

    return sent
