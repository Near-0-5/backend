from typing import Any, Literal, cast

from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from mypy_boto3_ivs.type_defs import GetStreamResponseTypeDef

from app.core.pagination import paginate_cursor
from app.core.utils.image_resizer import ImageResizer
from app.domains.artists.models import Artist
from app.domains.streams.admin.schemas import (
    ConcertCreateRequest,
    ConcertDetailResponse,
    IVSChannelSummary,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
    StreamIngestInfo,
    StreamIngestResponse,
    StreamLiveMetrics,
)
from app.domains.streams.models import (
    AccessLevel,
    Concert,
    ConcertArtist,
    ConcertSession,
    StreamChannel,
    StreamStatus,
)
from app.domains.notifications.service import notification_service
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider
from app.integrations.aws_ivs.client import logger


class StreamAdminService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider
        self.image_resizer = ImageResizer()

    async def create_concert(self, data: ConcertCreateRequest, user: User) -> Concert:
        """
        [Admin] 콘서트 생성
        """
        StreamPermission.must_be_admin(user)
        return await Concert.create(**data.model_dump())

    async def update_concert_thumbnail(
        self, concert_id: int, file: UploadFile, user: User
    ) -> Concert:
        """
        [Admin] 콘서트 썸네일 생성 및 수정
        """
        StreamPermission.must_be_admin(user)

        # 콘서트 있는지 확인
        concert = await Concert.get_or_none(id=concert_id)
        if not concert:
            raise HTTPException(status_code=404, detail="콘서트를 찾을 수 없습니다.")

        # 기존 이미지가 있다면 S3 폴더 삭제
        if concert.thumbnail_url:
            await self.image_resizer.delete_all_by_id_path(concert.thumbnail_url)

        # 새로운 이미지 리사이징 업로드
        path_prefix = f"concerts/{concert.id}/thumbnail"
        sizes = (300, 640, 1280)

        urls = await self.image_resizer.upload_square_resizes(
            image_file=file.file, sizes=sizes, path_prefix=path_prefix
        )

        # DB 업데이트
        img_url = urls.get("640")
        concert.thumbnail_url = img_url if img_url else ""
        await concert.save()

        return concert

    async def list_concerts(
        self, user: User, limit: int = 20, cursor: int | None = None
    ) -> tuple[list[Concert], int | None]:
        """
        [Admin] 콘서트 목록 조회
        """
        StreamPermission.must_be_admin(user)

        queryset = Concert.all()
        result: Any = await paginate_cursor(queryset, limit=limit, cursor=cursor, order_by="-id")

        concerts: list[Concert] = result[0]
        next_cursor: int | None = result[1]

        return concerts, next_cursor

    async def get_concert_detail(self, concert_id: int, user: User) -> ConcertDetailResponse:
        """
        [Admin] 콘서트 상세 조회(하위 세션 목록 포함)
        """
        StreamPermission.must_be_admin(user)

        concert = await Concert.get_or_none(id=concert_id).prefetch_related(
            "sessions__stream_channel"
        )

        if not concert:
            raise HTTPException(404, "존재하지 않는 콘서트입니다.")

        return ConcertDetailResponse.model_validate(concert)

    async def update_concert(
        self, concert_id: int, data: ConcertCreateRequest, user: User
    ) -> Concert:
        """
        [Admin] 콘서트 수정
        """
        StreamPermission.must_be_admin(user)

        concert = await Concert.get_or_none(id=concert_id)
        if not concert:
            raise HTTPException(404, "수정할 콘서트를 찾을 수 없습니다.")

        # 요청 데이터 반영 (exclude_unset=True로 보낸 값만 수정)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(concert, key, value)

        await concert.save()
        return concert

    async def delete_concert_with_infrastructure(self, concert_id: int, user: User) -> None:
        """
        [Admin] 콘서트 삭제 및 AWS IVS 채널 삭제
        """
        StreamPermission.must_be_admin(user)

        # 세션, 채널 정보 모두 가져옴
        concert = await Concert.get_or_none(id=concert_id).prefetch_related(
            "sessions__stream_channel"
        )

        if not concert:
            raise HTTPException(404, "삭제할 콘서트를 찾을 수 없습니다.")

        # 연결된 모든 세션의 AWS IVS 채널 먼저 삭제
        for session in list(concert.sessions):  # type: ignore[call-overload]
            if hasattr(session, "stream_channel") and session.stream_channel:
                try:
                    self.ivs_client.delete_channel(session.stream_channel.channel_arn)
                except Exception as e:
                    logger.warning(f"콘서트 삭제 중 세션({session.id})의 IVS 채널 삭제 실패: {e}")

        # 썸네일 삭제 (S3)
        if concert.thumbnail_url:
            await self.image_resizer.delete_all_by_id_path(concert.thumbnail_url)

        # DB 삭제(cascade)
        await concert.delete()

    async def create_session_with_infrastructure(
        self, concert_id: int, data: SessionCreateRequest, user: User
    ) -> SessionResponse:
        """
        [Admin] 콘서트 세션 생성 및 AWS IVS 채널 자동 발급
        """
        # 권한 체크
        StreamPermission.must_be_admin(user)

        # Concert 있나 확인
        concert = await Concert.get(id=concert_id)

        # 콘서트 세션 (실제 회차) 생성
        # channel_config는 IVS 설정용이므로 DB 모델 생성시에는 제외
        session_dict = data.model_dump(exclude={"channel_config", "artist_ids"})
        session = await ConcertSession.create(concert=concert, **session_dict)

        try:
            # 출연 아티스트 매핑
            if data.artist_ids:
                artists = await Artist.filter(id__in=data.artist_ids)
                if len(artists) != len(data.artist_ids):
                    found_ids = {a.id for a in artists}
                    missing = set(data.artist_ids) - found_ids
                    raise HTTPException(
                        status_code=400, detail=f"존재하지 않는 아티스트: {missing}"
                    )

                for artist in artists:
                    await ConcertArtist.create(session=session, artist=artist)

            # IVS 채널 생성 호출 (예외 처리 추가)
            config = data.channel_config

            ivs_res = self.ivs_client.create_channel(
                name=f"session-{session.id}",
                latency_mode=config.latency_mode.value,
                channel_type=config.channel_type.value,
                authorized=(session.access_level != AccessLevel.PUBLIC),
            )

            # DB 저장 시 필드명 snake_case 맞춤
            channel_arn = ivs_res["channel"]["arn"]
            stream_key_raw = ivs_res["streamKey"]["value"]

            # 채널 정보 DB 저장
            try:
                channel = StreamChannel(
                    session=session,
                    type=config.channel_type,
                    latency_mode=config.latency_mode,
                    channel_arn=channel_arn,
                    ingest_endpoint=ivs_res["channel"]["ingestEndpoint"],
                    playback_url=ivs_res["channel"]["playbackUrl"],
                    is_private=(session.access_level != AccessLevel.PUBLIC),
                )
                channel.set_stream_key(stream_key_raw)
                await channel.save()

            except Exception as db_error:
                # DB 저장 실패 시 AWS에 생성된 채널 삭제 (Cleanup)
                self.ivs_client.delete_channel(channel_arn)
                await session.delete()
                raise HTTPException(
                    status_code=500, detail=f"DB 저장 실패로 인프라를 롤백했습니다: {str(db_error)}"
                ) from db_error

        except HTTPException:
            if "session" in locals() and session.id:
                await session.delete()
            raise

        except Exception as e:
            # IVS 세팅 실패했으면 콘서트 세션 삭제
            if "session" in locals() and session.id:
                await session.delete()
            # AWS 권한 에러
            if (
                isinstance(e, ClientError)
                and e.response["Error"]["Code"] == "AccessDeniedException"
            ):
                raise HTTPException(500, "AWS 권한 부족") from e

            # 그 외 모든 에러
            raise HTTPException(500, f"IVS 채널 생성 실패: {str(e)}") from e

        from app.domains.streams.admin.schemas import IVSChannelSummary

        return SessionResponse(
            id=session.id,
            session_name=session.session_name,
            access_level=session.access_level,
            status=session.status,
            start_at=session.start_at,
            channel=IVSChannelSummary(
                arn=channel.channel_arn,
                ingest_endpoint=channel.ingest_endpoint,
                playback_url=channel.playback_url,
                latency_mode=channel.latency_mode,
                type=channel.type,
            ),
            value=stream_key_raw,  # 생성 시점에만 평문 노출
        )

    async def rotate_stream_key(self, session_id: int, user: User) -> str:
        """
        [Admin] 스트림 키 유출 시 재발급
        """
        StreamPermission.must_be_admin(user)

        session = await ConcertSession.get(id=session_id).prefetch_related("stream_channel")
        channel = session.stream_channel

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

    async def delete_session_with_infrastructure(self, session_id: int, user: User) -> None:
        """
        [Admin] 세션 삭제 및 연결된 IVS 채널 영구 제거
        """
        StreamPermission.must_be_admin(user)

        # 채널 정보 조회를 위해 관계 로드
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related("stream_channel")
        if not session:
            raise HTTPException(404, "존재하지 않는 세션입니다.")

        # IVS 채널 삭제
        if hasattr(session, "stream_channel") and session.stream_channel:
            try:
                self.ivs_client.delete_channel(session.stream_channel.channel_arn)
            except Exception as e:
                # 이미 AWS에서 지워졌을 수도 있으니까
                logger.warning(f"AWS 채널 삭제 실패(이미 제거되었을 수 있음): {str(e)}")

            # DB 삭제
            await session.delete()

    async def stop_stream_session(self, session_id: int, user: User) -> None:
        """
        [Admin] 라이브 방송 강제 중단 및 상태 종료 처리
        """
        StreamPermission.must_be_admin(user)

        session = await ConcertSession.get(id=session_id).prefetch_related("stream_channel")
        channel = session.stream_channel

        if not channel:
            raise HTTPException(404, "연결된 스트리밍 채널이 없습니다.")

        # IVS 송출 강제 중단
        try:
            self.ivs_client.stop_stream(channel.channel_arn)
        except Exception as e:
            # 방송 중이 아닐 때 stop 호출하면 안되니까
            logger.warning(f"AWS StopStream 호출 실패(이미 종료되었을 수 있음): {str(e)}")

        # DB 상태 업데이트
        session.status = StreamStatus.ENDED
        await session.save(update_fields=["status"])

    async def list_sessions_admin(
        self, user: User, limit: int = 20, cursor: int | None = None
    ) -> tuple[list[SessionResponse], int | None]:
        """
        [Admin] 라이브 방송 목록 조회
        """
        StreamPermission.must_be_admin(user)

        # DB 조회
        queryset = ConcertSession.all().prefetch_related("stream_channel", "concert")
        sessions, next_cursor = await paginate_cursor(
            queryset=queryset, limit=limit, cursor=cursor, order_by="-id"
        )

        # ENDED가 아닌 세션의 채널 ARN만 수집
        active_channel_arns = {
            s.stream_channel.channel_arn
            for s in sessions
            if hasattr(s, "stream_channel") and s.stream_channel and s.status != StreamStatus.ENDED
        }
        # 활성 채널만 AWS에 조회
        live_channel_arns = set()
        if active_channel_arns:
            try:
                # 건강 상태 확인
                live_streams = self.ivs_client.list_live_streams()
                live_channel_arns = {
                    s["channelArn"] for s in live_streams if s["channelArn"] in active_channel_arns
                }
            except Exception:
                pass  # AWS 조회 실패해도 DB 목록은 보여줌

        results = []
        for s in sessions:
            channel = getattr(s, "stream_channel", None)

            # DB는 READY지만 AWS에서 실제 송출 중이라면 LIVE로 표시
            display_status = s.status
            if (
                channel
                and (channel.channel_arn in live_channel_arns)
                and s.status != StreamStatus.ENDED
            ):
                display_status = StreamStatus.LIVE

            results.append(
                SessionResponse(
                    id=s.id,
                    session_name=s.session_name,
                    access_level=s.access_level,
                    start_at=s.start_at,
                    status=display_status,
                    channel=IVSChannelSummary(
                        arn=channel.channel_arn,
                        ingest_endpoint=channel.ingest_endpoint,
                        playback_url=channel.playback_url,
                        latency_mode=channel.latency_mode,
                        type=channel.type,
                    )
                    if channel
                    else None,
                )
            )

        return results, next_cursor

    async def get_session_admin_detail(self, session_id: int, user: User) -> SessionResponse:
        """
        [Admin] 콘서트 세션 상세 조회
        """
        StreamPermission.must_be_admin(user)
        session = await ConcertSession.get_or_none(id=session_id).prefetch_related("stream_channel")
        if not session:
            raise HTTPException(404, "해당 콘서트 세션을 찾을 수 없습니다.")

        channel = getattr(session, "stream_channel", None)

        return SessionResponse(
            id=session.id,
            session_name=session.session_name,
            access_level=session.access_level,
            start_at=session.start_at,
            status=session.status,
            channel=IVSChannelSummary(
                arn=channel.channel_arn,
                ingest_endpoint=channel.ingest_endpoint,
                playback_url=channel.playback_url,
                latency_mode=channel.latency_mode,
                type=channel.type,
            )
            if channel
            else None,
        )

    async def update_session_infrastructure(
        self, session_id: int, data: SessionUpdateRequest, user: User
    ) -> SessionResponse:
        """
        [Admin] 콘서트 세션 수정
        """
        StreamPermission.must_be_admin(user)

        # 동시 수정 방지 Lock
        session = (
            await ConcertSession.filter(id=session_id)
            .select_for_update()
            .prefetch_related("stream_channel")
            .first()
        )
        if not session:
            raise HTTPException(404, "해당 콘서트 세션을 찾을 수 없습니다.")

        channel = getattr(session, "stream_channel", None)
        start_at_before = session.start_at

        # DB 수정
        update_dict = data.model_dump(exclude={"channel_config", "artist_ids"}, exclude_unset=True)
        for key, value in update_dict.items():
            setattr(session, key, value)

        # 아티스트 정보 수정
        if data.artist_ids is not None:
            # 기존 매핑 삭제 후 재생성
            await ConcertArtist.filter(session=session).delete()
            if data.artist_ids:
                artists = await Artist.filter(id__in=data.artist_ids)
                for artist in artists:
                    await ConcertArtist.create(session=session, artist=artist)

        # AWS IVS 채널 설정 동기화
        if data.channel_config and channel:
            config = data.channel_config

            # Private 여부 결정
            current_access = update_dict.get("access_level", session.access_level)
            is_private = current_access != AccessLevel.PUBLIC

            # 변경할 값 확인 (없으면 기존 값 유지)
            new_latency = cast(
                "Literal['LOW', 'NORMAL']",
                config.latency_mode.value if config.latency_mode else channel.latency_mode.value,
            )
            new_type = cast(
                "Literal['ADVANCED_HD', 'ADVANCED_SD', 'BASIC', 'STANDARD']",
                config.channel_type.value if config.channel_type else channel.type.value,
            )

            # AWS API 호출
            self.ivs_client.update_channel(
                channel_arn=channel.channel_arn,  # type: ignore
                name=f"session-{session.id}",  # 이름 강제 동기화
                latencyMode=new_latency,
                type=new_type,
                authorized=is_private,
            )

            # DB 채널 정보 업데이트
            if config.latency_mode:
                channel.latency_mode = config.latency_mode
            if config.channel_type:
                channel.type = config.channel_type
            channel.is_private = is_private
            await channel.save()

        await session.save()

        if data.start_at is not None and data.start_at != start_at_before:
            await notification_service.reschedule_session_notifications(session.id, session=session)

        # 업데이트된 정보로 다시 조회하여 반환
        return await self.get_session_admin_detail(session_id, user)

    async def _sync_session_status_with_aws(
        self, session: ConcertSession, channel: StreamChannel
    ) -> tuple[StreamStatus, GetStreamResponseTypeDef | None]:
        """AWS 실시간 상태와 DB 상태 동기화"""
        stream_res = self.ivs_client.get_stream_health(channel.channel_arn)
        is_live = stream_res is not None and "stream" in stream_res

        new_status = StreamStatus.LIVE if is_live else StreamStatus.READY

        # ENDED 상태는 보존
        if session.status != StreamStatus.ENDED and session.status != new_status:
            session.status = new_status
            await session.save(update_fields=["status"])

        return session.status, stream_res

    # ================================= ivs 송출 테스트용  =================================

    async def get_stream_ingest_info(self, session_id: int, user: User) -> StreamIngestResponse:
        """
        [Admin] 송출 상세 정보 조회, 실시간 상태 확인
        """
        # 관리자 권한 체크
        StreamPermission.must_be_admin(user)

        # DB 조회
        session = await ConcertSession.get(id=session_id).prefetch_related(
            "stream_channel", "concert"
        )
        channel = session.stream_channel

        if not channel:
            raise HTTPException(404, "해당 세션에 연결된 IVS 채널이 없습니다.")

        playback_token = None

        # 채널이 비공개(Private) 설정이 되어 있다면 토큰을 발급합니다.
        if channel.is_private:
            playback_token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn,
                viewer_id=f"admin-{user.id}",
                duration_sec=3600,  # 1시간
            )

        # AWS IVS 헬스체크(방송 중 아니면 None)
        stream_res = self.ivs_client.get_stream_health(channel.channel_arn)
        is_live = stream_res is not None and "stream" in stream_res

        # DB 상태 동기화(AWS는 LIVE인데 DB가 READY면 업데이트)
        new_status = StreamStatus.LIVE if is_live else StreamStatus.READY

        # 이미 종료된 방송(ENDED)은 함부로 바꾸지 않도록 방어
        if session.status != StreamStatus.ENDED and session.status != new_status:
            session.status = new_status
            await session.save(update_fields=["status"])

        # 방송 중 실시간 메트릭 구성
        live_metrics = None
        if is_live and stream_res:
            s = stream_res["stream"]
            live_metrics = StreamLiveMetrics(
                health=s.get("health"),  # HEALTHY, STARVING, UNKNOWN
                viewer_count=s.get("viewerCount", 0),
                start_time=s.get("startTime"),
                state=s.get("state"),
            )

        return StreamIngestResponse(
            session_id=session.id,
            is_live=is_live,
            concert_title=session.concert.title,
            ingest_info=StreamIngestInfo(
                ingest_endpoint=channel.ingest_endpoint,  # OBS 서버 (rtmps://)
                value=channel.get_stream_key(),  # OBS 스트림 키 (복호화)
            ),
            playback_url=channel.playback_url,
            playback_token=playback_token,
            live_metrics=live_metrics,
        )
