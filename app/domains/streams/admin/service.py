from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.domains.artists.models import Artist
from app.domains.streams.admin.schemas import (
    ConcertCreateRequest,
    SessionCreateRequest,
    SessionResponse,
)
from app.domains.streams.models import (
    AccessLevel,
    Concert,
    ConcertArtist,
    ConcertSession,
    StreamChannel,
)
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient


class StreamAdminService:
    def __init__(self, ivs_client: IVSClient):
        self.ivs_client = ivs_client

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
                channel_arn=channel.channel_arn,
                ingest_endpoint=channel.ingest_endpoint,
                playback_url=channel.playback_url,
                latency_mode=channel.latency_mode,
                channel_type=channel.type,
            ),
            stream_key=stream_key_raw,  # 생성 시점에만 평문 노출
        )
