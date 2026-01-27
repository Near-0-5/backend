from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from fastapi import WebSocket, WebSocketDisconnect
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from app.core.config import KST, now_kst
from app.domains.notifications.manager import notification_manager
from app.domains.notifications.models import ConcertNoti, NotiKind, NotiStatus, UserNoti
from app.domains.notifications.schemas import (
    NotificationEvent,
    NotificationItem,
)
from app.domains.streams.models import ConcertSession, StreamStatus
from app.domains.users.models import User

_SCHEDULE_OFFSETS = {
    NotiKind.HOUR_1: timedelta(hours=1),
    NotiKind.MIN_30: timedelta(minutes=30),
    NotiKind.START: timedelta(),
}


def _normalize_start_at(start_at: datetime) -> datetime:
    return start_at.replace(tzinfo=KST) if start_at.tzinfo is None else start_at.astimezone(KST)


def _build_schedule(start_at: datetime) -> dict[NotiKind, datetime]:
    start_at = _normalize_start_at(start_at)
    schedule = {kind: start_at - offset for kind, offset in _SCHEDULE_OFFSETS.items()}
    schedule[NotiKind.DAY_BEFORE] = (start_at - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return schedule


def _build_content(session: ConcertSession, kind: NotiKind) -> tuple[str, str]:
    start_at = _normalize_start_at(session.start_at)
    start_str = start_at.strftime("%Y-%m-%d %H:%M")

    if kind == NotiKind.DAY_BEFORE:
        prefix = "내일 라이브 시작 예정"
    elif kind == NotiKind.HOUR_1:
        prefix = "라이브 시작 1시간 전"
    elif kind == NotiKind.MIN_30:
        prefix = "라이브 시작 30분 전"
    else:
        prefix = "라이브 시작"

    title = f"{session.concert.title} 라이브 알림"
    message = f"{prefix}: {session.session_name} ({start_str})"
    return title, message


class NotificationService:
    async def get_user_settings(self, user_id: int) -> UserNoti:
        noti = await UserNoti.get_or_none(user_id=user_id)
        if noti:
            return noti
        return await UserNoti.create(user_id=user_id)

    async def list_user_notifications(
        self,
        user_id: int,
        *,
        status: NotiStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ConcertNoti], int]:
        query = ConcertNoti.filter(user_id=user_id)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        items = await query.order_by("-send_at").offset(offset).limit(limit)
        return list(items), total

    async def schedule_session_notifications(
        self, session_id: int, *, session: ConcertSession | None = None
    ) -> int:
        """세션 알림 스케줄 생성 후 생성된 알림 수 반환."""
        if session is None:
            session = await ConcertSession.get(id=session_id)
        await session.fetch_related("concert", "lineup")

        if session.status == StreamStatus.ENDED:
            return 0

        user_ids = await self._resolve_target_user_ids(session)
        if not user_ids:
            return 0

        schedule_map = _build_schedule(session.start_at)
        total_created = 0

        for kind, send_at in schedule_map.items():
            existing_ids = cast(
                "list[int]",
                await ConcertNoti.filter(
                    session_id=session.id, kind=kind, user_id__in=user_ids
                ).values_list("user_id", flat=True),
            )
            missing_ids = sorted(set(user_ids) - set(existing_ids))
            if not missing_ids:
                continue

            title, message = _build_content(session, kind)
            notis = [
                ConcertNoti(
                    user_id=user_id,
                    session_id=session.id,
                    kind=kind,
                    title=title,
                    message=message,
                    send_at=send_at,
                    status=NotiStatus.PENDING,
                )
                for user_id in missing_ids
            ]

            try:
                await ConcertNoti.bulk_create(notis, batch_size=500)
                total_created += len(notis)
            except IntegrityError:
                created = 0
                for noti in notis:
                    user_id = noti.user_id
                    session_id = noti.session_id
                    _, is_created = await ConcertNoti.get_or_create(
                        user_id=user_id,
                        session_id=session_id,
                        kind=noti.kind,
                        defaults={
                            "title": noti.title,
                            "message": noti.message,
                            "send_at": noti.send_at,
                            "status": noti.status,
                        },
                    )
                    if is_created:
                        created += 1
                total_created += created

        return total_created

    async def schedule_upcoming_sessions(self, hours_ahead: int = 24) -> int:
        """지금부터 N시간 이내 시작하는 세션들의 알림을 생성."""
        now = now_kst()
        until = now + timedelta(hours=hours_ahead)

        sessions = (
            await ConcertSession.filter(
                start_at__gte=now,
                start_at__lte=until,
            )
            .exclude(status=StreamStatus.ENDED)
            .prefetch_related("concert", "lineup")
        )

        total = 0
        for session in sessions:
            total += await self.schedule_session_notifications(session.id, session=session)
        return total

    async def deliver_concert_notification(self, noti: ConcertNoti) -> bool:
        """알림을 발행하고 연결된 WS로 전달."""
        payload = NotificationEvent(notification=NotificationItem.model_validate(noti)).model_dump(
            mode="json"
        )
        user_id = noti.user_id
        await notification_manager.publish(str(user_id), payload)
        return True

    async def handle_ws_connection(self, ws: WebSocket, *, user_id: int) -> None:
        user_key = str(user_id)
        try:
            await notification_manager.ensure_subscriber()
            await notification_manager.connect(user_key, ws)
        except RuntimeError:
            await ws.close(code=1008)
            return

        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await notification_manager.disconnect(user_key, ws)

    async def _resolve_target_user_ids(self, session: ConcertSession) -> list[int]:
        lineup = await session.lineup.all()
        artist_ids = [artist.id for artist in lineup]
        filters: list[Q] = []

        if artist_ids:
            filters.append(Q(noti_setting__artist_noti=True, followed_artists__id__in=artist_ids))

        filters.append(Q(fav_categories__category=session.concert.category))

        combined = filters[0]
        for clause in filters[1:]:
            combined |= clause

        users = cast(
            "list[int]",
            await User.filter(noti_setting__live_noti=True)
            .filter(combined)
            .distinct()
            .values_list("id", flat=True),
        )
        return list(users)


notification_service = NotificationService()
