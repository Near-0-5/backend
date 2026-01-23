from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.domains.artists.models import Artist
from app.domains.streams.admin.schemas import (
    ConcertCreateRequest,
    SessionCreateRequest,
    SessionResponse,
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
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider
from app.integrations.aws_ivs.client import logger


class StreamAdminService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider

    async def create_concert(self, data: ConcertCreateRequest, user: User) -> Concert:
        """
        [Admin] 콘서트 생성
        """
        StreamPermission.must_be_admin(user)
        return await Concert.create(**data.model_dump())

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
