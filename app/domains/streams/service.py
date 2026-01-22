from typing import Any

from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.domains.artists.models import Artist
from app.domains.streams.models import (
    AccessLevel,
    Concert,
    ConcertArtist,
    ConcertSession,
    StreamChannel,
)
from app.domains.streams.permissions import StreamPermission
from app.domains.streams.schemas import ConcertCreateRequest, SessionCreateRequest, SessionResponse
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


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

        # 출연 아티스트 매핑
        if data.artist_ids:
            artists = await Artist.filter(id__in=data.artist_ids)
            if len(artists) != len(data.artist_ids):
                found_ids = {a.id for a in artists}
                missing = set(data.artist_ids) - found_ids
                raise HTTPException(status_code=400, detail=f"존재하지 않는 아티스트: {missing}")

            for artist in artists:
                await ConcertArtist.create(session=session, artist=artist)

        # IVS 채널 생성 호출 (예외 처리 추가)
        config = data.channel_config
        try:
            ivs_res = self.ivs_client.create_channel(
                name=f"session-{session.id}",
                latency_mode=config.latency_mode.value,
                channel_type=config.channel_type.value,
                authorized=(session.access_level != AccessLevel.PUBLIC),
            )
        except Exception as e:
            if (
                isinstance(e, ClientError)
                and e.response["Error"]["Code"] == "AccessDeniedException"
            ):
                raise HTTPException(
                    status_code=500, detail="AWS 권한 부족 (IVS Access Denied)"
                ) from e
            raise HTTPException(status_code=500, detail=f"IVS 채널 생성 실패: {str(e)}") from e

        # DB 저장 및 롤백 (채널만 생김 방지)
        channel_arn = ivs_res["channel"]["arn"]
        stream_key_raw = ivs_res["streamKey"]["value"]

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
            raise HTTPException(
                status_code=500, detail=f"DB 저장 실패로 인프라를 롤백했습니다: {str(db_error)}"
            ) from db_error

        from app.domains.streams.schemas import IVSChannelSummary

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


class StreamUserService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider

    async def get_viewing_credentials(self, session_id: int, user: User) -> dict[str, Any]:
        """
        [User] 시청 권한 확인 및 최초 재생/채팅 토큰 발급
        """
        session = await ConcertSession.get(id=session_id).prefetch_related("stream_channel")

        # 유저 권한 증명
        await StreamPermission.verify_playback_access(user, session)

        channel: StreamChannel = session.stream_channel
        playback_url: str = channel.playback_url

        # 비공개 채널이면 토큰 서명
        if channel.is_private:
            token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn, viewer_id=str(user.id)
            )
            playback_url = f"{playback_url}?token={token}"

        # 내부 세션 토큰
        internal_tokens = self.playback_provider.sign_internal_tokens(
            user_id=str(user.id), stream_id=str(channel.id)
        )

        return {
            "playback_url": playback_url,
            "stream_id": channel.id,
            "access_token": internal_tokens["access_token"],
            "refresh_token": internal_tokens["refresh_token"],
        }

    async def refresh_viewing_session(
        self, session_id: int, user: User, refresh_token: str
    ) -> dict[str, Any]:
        """
        [User] 시청 중인 세션 연장 (아마존 권장: 연장 시마다 권한 재검증)
        """
        # 대상 세션, 채널 조회
        session = await ConcertSession.get(id=session_id).prefetch_related("stream_channel")

        # 갱신 시점에 다시 권한 체크
        await StreamPermission.verify_playback_access(user, session)

        # 기존 리프레시 토큰으로 새 토큰 Access/Refresh 발급
        new_tokens = self.playback_provider.rotate_tokens(refresh_token)

        # IVS 재생 토큰 새 유효기간으로 재서명
        channel: StreamChannel = session.stream_channel
        playback_url: str = channel.playback_url

        if channel.is_private:
            token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn, viewer_id=str(user.id)
            )
            playback_url = f"{playback_url}?token={token}"

        return {
            "playback_url": playback_url,
            "access_token": new_tokens["access_token"],
            "refresh_token": new_tokens["refresh_token"],
        }
