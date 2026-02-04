from contextlib import suppress

from fastapi import HTTPException
from mypy_boto3_ivs.type_defs import CreateChannelResponseTypeDef, GetStreamResponseTypeDef
from tortoise.transactions import in_transaction

from app.core.config import now_kst, settings
from app.core.pagination import paginate_cursor
from app.core.utils.image_resizer import ImageResizer
from app.domains.artists.models import Artist
from app.domains.concerts.models import Concert
from app.domains.notifications.tasks import (
    dispatch_due_notifications,
    reschedule_session_notifications,
    schedule_session_notifications,
)
from app.domains.streams.admin.schemas import (
    ChannelConfig,
    IVSChannelSummary,
    IVSUpdateConfig,
    SessionCreateRequest,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
    StreamIngestResponse,
    StreamLiveMetrics,
    StreamWebhookPayload,
)
from app.domains.streams.models import (
    AccessLevel,
    ConcertArtist,
    ConcertSession,
    StreamChannel,
    StreamSession,
    StreamStatus,
)
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider
from app.integrations.aws_ivs.client import logger


class StreamAdminService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider
        self.image_resizer = ImageResizer()

    # ==============================================================================================
    async def _get_concert_or_raise(self, concert_id: int) -> Concert:
        """콘서트 조회"""
        concert = await Concert.get_or_none(id=concert_id)
        if not concert:
            raise HTTPException(404, f"Concert {concert_id} not found")
        return concert

    async def _get_session_with_channel_or_raise(self, session_id: int) -> ConcertSession:
        """콘서트 세션 + 연결된 IVS Channel 조회"""
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related(
            "stream_channel", "concert"
        )
        if not session:
            raise HTTPException(404, f"Concert Session {session_id} not found")
        return session

    async def _validate_and_get_artists(self, artist_ids: list[int] | None) -> list[Artist]:
        """출연 아티스트 검증"""
        if not artist_ids:
            return []

        artists = await Artist.filter(id__in=artist_ids)

        if len(artists) != len(artist_ids):
            found_ids = {a.id for a in artists}
            missing = set(artist_ids) - found_ids
            raise HTTPException(404, f"Artist(s) {missing} not found")

        return list(artists)

    def _create_ivs_channel_infra(
        self, session: ConcertSession, config: ChannelConfig
    ) -> CreateChannelResponseTypeDef:
        """AWS IVS 채널 생성 API 호출"""

        return self.ivs_client.create_channel(
            name=f"session-{session.id}",
            latency_mode=config.latency_mode.value,
            channel_type=config.channel_type.value,
            authorized=(session.access_level != AccessLevel.PUBLIC),
        )

    def _update_ivs_channel_infra(
        self, session: ConcertSession, channel: StreamChannel, config: IVSUpdateConfig
    ) -> None:
        """AWS IVS 채널 설정 업데이트 API 호출"""

        self.ivs_client.update_channel(
            channel_arn=channel.channel_arn,  # type: ignore[call-arg]
            name=f"session-{session.id}",
            latencyMode=(
                config.latency_mode.value if config.latency_mode else channel.latency_mode.value
            ),
            type=(config.channel_type.value if config.channel_type else channel.type.value),
            authorized=(session.access_level != AccessLevel.PUBLIC),
        )

    async def _sync_and_get_health(
        self, session: ConcertSession, channel: StreamChannel
    ) -> tuple[StreamStatus, GetStreamResponseTypeDef | None]:
        """AWS 실시간 상태 동기화 metrics 확보"""
        stream_res = self.ivs_client.get_stream_health(channel.channel_arn)
        is_live = stream_res is not None and "stream" in stream_res

        new_status = StreamStatus.LIVE if is_live else StreamStatus.READY

        if session.status != StreamStatus.ENDED and session.status != new_status:
            session.status = new_status
            await session.save(update_fields=["status"])

        return session.status, stream_res

    async def _cleanup_on_failure(
        self, session_id: int | None, channel_arn: str | None = None
    ) -> None:
        """실패 시 롤백 - 인프라, DB 데이터 삭제"""

        if channel_arn:
            try:
                self.ivs_client.delete_channel(channel_arn)
            except Exception as e:
                logger.error(f"Cleanup AWS failed : {e}")

        if session_id:
            await ConcertSession.filter(id=session_id).delete()

    def _map_channel_summary(self, channel: StreamChannel | None) -> IVSChannelSummary | None:
        if not channel:
            return None

        return IVSChannelSummary(
            arn=channel.channel_arn,
            ingest_endpoint=channel.ingest_endpoint,
            playback_url=channel.playback_url,
            latency_mode=channel.latency_mode,
            type=channel.type,
        )

    def _map_to_session_response(
        self, session: ConcertSession, channel: StreamChannel | None, raw_key: str | None = None
    ) -> SessionResponse:
        """SessionResponse 스키마로 변환"""

        return SessionResponse(
            id=session.id,
            session_name=session.session_name,
            access_level=session.access_level,
            start_at=session.start_at,
            status=session.status,
            channel=self._map_channel_summary(channel),
            value=raw_key or (channel.get_stream_key() if channel else None),
        )

    def _map_to_session_list_item(
        self,
        session: ConcertSession,
        *,
        display_status: StreamStatus,
    ) -> SessionListItem:
        concert = session.concert

        return SessionListItem(
            id=session.id,
            concert_title=concert.title,
            session_name=session.session_name,
            thumbnail_url=concert.thumbnail_url,
            category=concert.category,
            status=display_status,
            start_at=session.start_at,
        )

    def _map_to_ingest_response(
        self,
        session: ConcertSession,
        channel: StreamChannel,
        stream_res: GetStreamResponseTypeDef | None,
        playback_token: str | None = None,
    ) -> StreamIngestResponse:
        """StreamIngestResponse 스키마로 변환"""

        stream = stream_res.get("stream") if stream_res else None

        live_metrics = None
        if stream:
            from datetime import datetime

            live_metrics = StreamLiveMetrics(
                health=stream.get("health"),
                viewer_count=stream.get("viewerCount"),
                start_time=stream.get("startTime", datetime.now()),  # 기본값 처리
                state=stream.get("state", "LIVE"),  # 기본 LIVE
            )

        return StreamIngestResponse.model_validate(
            {
                "session_id": session.id,
                "session_name": session.session_name,
                "is_live": stream is not None,
                "concert_title": session.concert.title,
                "playback_url": channel.playback_url,
                "playback_token": playback_token,
                "ingest_info": {
                    "ingest_endpoint": channel.ingest_endpoint,
                    "value": channel.get_stream_key(),
                },
                "live_metrics": live_metrics,
            }
        )

    # ==============================================================================================
    async def create_session(
        self, concert_id: int, data: SessionCreateRequest, user: User | None = None
    ) -> SessionResponse:
        """
        [Admin] 콘서트 세션 생성 (channel은 none)
        """
        # 콘서트, 아티스트 검증
        concert = await self._get_concert_or_raise(concert_id)
        artists = await self._validate_and_get_artists(data.artist_ids)

        async with in_transaction():
            # channel_config는 IVS 설정용이므로 DB 모델 생성시에는 제외
            session = await ConcertSession.create(
                concert=concert, **data.model_dump(exclude={"channel_config", "artist_ids"})
            )
            for artist in artists:
                await ConcertArtist.create(session=session, artist=artist)

        return self._map_to_session_response(session, channel=None)

    async def provision_channel(
        self, session_id: int, user: User | None, config: ChannelConfig
    ) -> SessionResponse:
        """
        [Admin] 기존 세션에 AWS IVS 채널 발급
        """
        session = await self._get_session_with_channel_or_raise(session_id)

        if session.stream_channel:
            raise HTTPException(400, "Channel already exists for this session")

        created_arn = None

        try:
            ivs_res = self._create_ivs_channel_infra(session, config)
            created_arn = ivs_res["channel"]["arn"]
            raw_key = ivs_res["streamKey"]["value"]

            channel = StreamChannel(
                session=session,
                channel_arn=created_arn,
                ingest_endpoint=ivs_res["channel"]["ingestEndpoint"],
                playback_url=ivs_res["channel"]["playbackUrl"],
                latency_mode=config.latency_mode,
                type=config.channel_type,
                is_private=(session.access_level != AccessLevel.PUBLIC),
            )
            channel.set_stream_key(raw_key)
            await channel.save()

            schedule_session_notifications.delay(session.id)

            return self._map_to_session_response(session, channel, raw_key)

        except Exception as e:
            await self._cleanup_on_failure(session_id=None, channel_arn=created_arn)
            logger.exception("IVS Channel provisioning failed")
            raise HTTPException(500, "Failed to provision IVS Channel") from e

    async def update_session(
        self, session_id: int, data: SessionUpdateRequest, user: User | None
    ) -> SessionResponse:
        """
        [Admin] 콘서트 세션 수정
        """
        session = await self._get_session_with_channel_or_raise(session_id)
        channel = session.stream_channel
        start_at_before = session.start_at

        async with in_transaction():
            # 아티스트 동기화
            if data.artist_ids is not None:
                artists = await self._validate_and_get_artists(data.artist_ids)
                await ConcertArtist.filter(session=session).delete()
                for artist in artists:
                    await ConcertArtist.create(session=session, artist=artist)

            # 세션 정보 업데이트
            update_dict = data.model_dump(
                exclude={"channel_config", "artist_ids"}, exclude_unset=True
            )
            for key, value in update_dict.items():
                setattr(session, key, value)

            await session.save()

        if data.start_at and data.start_at != start_at_before:
            reschedule_session_notifications.delay(session.id)

        return self._map_to_session_response(session, channel)

    async def update_channel_config(
        self, session_id: int, config: IVSUpdateConfig, user: User | None
    ) -> SessionResponse:
        """
        [Admin] 콘서트 채널 수정
        """
        session = await self._get_session_with_channel_or_raise(session_id)
        channel = session.stream_channel
        # 인프라 설정 변경
        if config and channel:
            self._update_ivs_channel_infra(session, channel, config)

            # DB 채널 상태 동기화
            if config.latency_mode:
                channel.latency_mode = config.latency_mode
            if config.channel_type:
                channel.type = config.channel_type
            channel.is_private = session.access_level != AccessLevel.PUBLIC
            await channel.save()

        return self._map_to_session_response(session, channel)

    async def list_sessions_admin(
        self,
        user: User,
        limit: int = 20,
        cursor: int | None = None,
    ) -> SessionListResponse:
        """
        [Admin] 라이브 방송 목록 조회
        """
        queryset = ConcertSession.all().prefetch_related("stream_channel", "concert")
        sessions, next_cursor = await paginate_cursor(
            queryset=queryset, cursor=cursor, limit=limit, order_by="-id"
        )
        items = [self._map_to_session_list_item(s, display_status=s.status) for s in sessions] or []
        return SessionListResponse(items=items, next_cursor=next_cursor)

    async def get_session_admin_detail(self, session_id: int, user: User) -> SessionResponse:
        """
        [Admin] 콘서트 세션 상세 조회
        """
        session = await self._get_session_with_channel_or_raise(session_id)
        channel = session.stream_channel
        if not channel:
            raise HTTPException(404, f"Channel {channel.id} not found")

        return self._map_to_session_response(session, channel)

    async def delete_session_with_infrastructure(self, session_id: int, user: User) -> None:
        """
        [Admin] 세션 삭제 및 연결된 IVS 채널 영구 제거
        """
        session = await self._get_session_with_channel_or_raise(session_id)
        channel = getattr(session, "stream_channel", None)

        if channel:
            try:
                self.ivs_client.delete_channel(channel.channel_arn)
            except Exception as e:
                logger.warning(f"AWS Delete Fail: {e}")

            await session.delete()

    async def stop_stream_session(self, session_id: int, user: User) -> None:
        """
        [Admin] 라이브 방송 강제 중단 및 상태 종료 처리
        """

        session = await self._get_session_with_channel_or_raise(session_id)
        if not session.stream_channel:
            raise HTTPException(404, f"Session {session_id} not found")

        with suppress(Exception):
            self.ivs_client.stop_stream(session.stream_channel.channel_arn)

        session.status = StreamStatus.ENDED
        await session.save(update_fields=["status"])

    async def rotate_stream_key(self, session_id: int, user: User) -> str:
        """
        [Admin] 스트림 키 유출 시 재발급
        """

        session = await self._get_session_with_channel_or_raise(session_id)
        channel = session.stream_channel
        if not channel:
            raise HTTPException(404, f"Channel {channel.id} not found")

        # 스트림 키 삭제
        existing_keys = self.ivs_client.list_all_stream_keys(channel.channel_arn)
        for k in existing_keys:
            self.ivs_client.delete_stream_key(k["arn"])

        # 새 스트림 키 생성
        new_key_res = self.ivs_client.create_stream_key(channel.channel_arn)
        new_key_raw = new_key_res["streamKey"]["value"]

        # DB 업데이트 (암호화 저장)
        channel.set_stream_key(new_key_raw)
        await channel.save(update_fields=["stream_key_encrypted"])

        return new_key_raw

    # ==============================================================================================
    async def handle_ivs_webhook(self, payload: StreamWebhookPayload) -> None:
        """
        IVS 상태 Webhook
        """
        detail = payload.detail
        channel = await StreamChannel.get_or_none(
            channel_arn=payload.resources[0]
        ).prefetch_related("session")
        if not channel:
            return  # 알 수 없는 채널 무시

        session: ConcertSession = channel.session
        now = now_kst()

        # 방송 시작 (Stream Start)
        if detail.event_name == "Stream Start":
            session.status = StreamStatus.LIVE
            await session.save(update_fields=["status"])
            # 스트리밍 이력 생성
            await StreamSession.create(session=session, stream_id=detail.stream_id, started_at=now)
            dispatch_due_notifications.delay()  # 라이브 시작 알림

        # 방송 종료 (Stream End)
        elif detail.event_name == "Stream End":
            session.status = (
                StreamStatus.ENDED
            )  # if (session.end_at and now > session.end_at) else StreamStatus.READY
            await session.save(update_fields=["status"])

            stream_hist = await StreamSession.get_or_none(stream_id=detail.stream_id)
            if stream_hist:
                stream_hist.ended_at = now
                await stream_hist.save(update_fields=["ended_at"])

    async def reopen_session(self, session_id: int, user: User) -> None:
        """관리자가 종료된 세션을 다시 활성화"""
        session = await self._get_session_with_channel_or_raise(session_id)

        if session.status != StreamStatus.ENDED:
            raise HTTPException(400, f"Only ENDED sessions can be reactivated: {session.status}")
        session.status = StreamStatus.READY
        await session.save(update_fields=["status"])

    # ==============================================================================================
    async def get_stream_ingest_info(self, session_id: int, user: User) -> StreamIngestResponse:
        """
        [Admin] 송출 상세 정보 조회, 실시간 상태 확인
        """
        session = await self._get_session_with_channel_or_raise(session_id)
        channel = session.stream_channel
        if not channel:
            raise HTTPException(404, f"Channel {channel.id} not found")

        # AWS IVS 헬스체크
        _, stream_res = await self._sync_and_get_health(session, channel)

        playback_token = None
        if channel.is_private:
            playback_token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn,
                viewer_id=f"id: {user.id}",
                duration_sec=settings.ADMIN_IVS_PLAYBACK_TOKEN_EXPIRATION_SEC,
            )

        return self._map_to_ingest_response(session, channel, stream_res, playback_token)
