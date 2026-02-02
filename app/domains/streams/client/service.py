from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q

from app.core.config import settings
from app.core.pagination import paginate_cursor
from app.domains.streams.client.schemas import (
    ArtistItem,
    SessionDetailResponse,
)
from app.domains.streams.models import CategoryType, ConcertSession, StreamChannel, StreamStatus
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


class StreamUserService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider

    async def get_viewing_credentials(self, session_id: int, user: User) -> dict[str, Any]:
        """
        [User] 시청 권한 확인 및 최초 재생/채팅 토큰 발급
        """
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related("stream_channel")

        if not session:
            raise HTTPException(404, "콘서트 세션 정보를 찾을 수 없습니다.")
        # 유저 권한 증명
        await StreamPermission.verify_playback_access(user, session)

        channel: StreamChannel = session.stream_channel
        playback_url: str = channel.playback_url

        # 비공개 채널이면 토큰 서명
        if channel.is_private:
            token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn,
                viewer_id=str(user.id),
                duration_sec=settings.ADMIN_IVS_PLAYBACK_TOKEN_EXPIRATION_SEC,
            )
            playback_url = f"{playback_url}?token={token}"

        return {
            "playback_url": playback_url,
            "stream_id": channel.id,
        }

    async def refresh_playback_url(
        self,
        session_id: int,
        user: User,
    ) -> str:
        """
        [User] 시청 중인 세션 연장 (아마존 권장: 연장 시마다 권한 재검증)
        """
        # 대상 세션, 채널 조회
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related("stream_channel")

        if not session:
            raise HTTPException(404, "콘서트 세션 정보를 찾을 수 없습니다.")

        # 갱신 시점에 다시 권한 체크
        await StreamPermission.verify_playback_access(user, session)
        channel = session.stream_channel

        # 공개 채널이면 그냥 URL 반환
        if not channel.is_private:
            return channel.playback_url

        # 비공개 채널이면 토큰 서명
        new_token = self.playback_provider.sign_playback_token(
            channel_arn=session.stream_channel.channel_arn,
            viewer_id=str(user.id),
            duration_sec=settings.ADMIN_IVS_PLAYBACK_TOKEN_EXPIRATION_SEC,
        )
        refreshed_playback_url = f"{channel.playback_url}?token={new_token}"

        return refreshed_playback_url

    async def list_sessions(
        self,
        status: StreamStatus | None = None,
        category: CategoryType | None = None,
        artist_name: str | None = None,
        title: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        order_by: str = "latest",
        cursor: int | None = None,
        limit: int = 10,
    ) -> tuple[Sequence[ConcertSession], int | None]:
        """
        [User] 스트리밍 목록 조회 (커서 페이징)
        - 상태, 카테고리(장르) 필터
        - 제목 or 아티스트 검색
        - 날짜 범위 필터
        - 정렬 (latest / oldest)
        """
        # 필터링
        filters = Q()
        if status:  # 상태별
            filters &= Q(status=status)
        if category:  # 장르별
            filters &= Q(concert__category=category)

        if artist_name:
            artist_name = artist_name.strip()
            filters &= Q(lineup__stage_name__icontains=artist_name)

        if title:
            title = title.strip()
            filters &= Q(concert__title__icontains=title)

        if from_date:
            filters &= Q(start_at__gte=from_date)

        if to_date:
            to_datetime = datetime.combine(to_date, time.max)
            filters &= Q(start_at__lte=to_datetime)

        queryset = (
            ConcertSession.filter(filters)
            .prefetch_related("concert", "lineup", "stream_channel")
            .distinct()
        )

        # 정렬
        order = "id" if order_by == "oldest" else "-id"

        return await paginate_cursor(
            queryset=queryset,
            cursor=cursor,
            limit=limit,
            order_by=order,
        )

    async def get_sessions_detail(self, user: User, session_id: int) -> SessionDetailResponse:
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related(
            "concert", "artist_mappings__artist"
        )

        if not session:
            raise HTTPException(404, "공연 정보를 찾을 수 없습니다.")

        await StreamPermission.verify_playback_access(user, session)

        lineup_items = [
            ArtistItem(
                id=m.artist.id,
                name=m.artist.stage_name,
                type=m.artist.group_type,
                profile_img_url=m.artist.profile_img_url,
                agency=m.artist.agency,
                is_main=m.is_main,
            )
            for m in session.artist_mappings
        ]

        return SessionDetailResponse(
            id=session.id,
            concert_title=session.concert.title,
            session_name=session.session_name,
            thumbnail_url=session.concert.thumbnail_url,
            category=session.concert.category,
            status=session.status,
            description=session.concert.description,
            lineup=lineup_items,
            start_at=session.start_at,
            end_at=session.end_at,
        )

    async def get_status(self, session_id: int) -> StreamStatus:
        session = await ConcertSession.get_or_none(id=session_id)
        if not session:
            raise HTTPException(404, "콘서트 세션 정보를 찾을 수 없습니다.")
        return session.status
