from typing import Any

from app.domains.streams.models import ConcertArtist

from app.domains.streams.models import AccessLevel, Concert, StreamChannel
from app.domains.streams.permissions import StreamPermission
from app.domains.streams.schemas import ConcertCreateRequest
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


class StreamService:
    def __init__(self, ivs_client: IVSClient, playback_provider: IVSPlaybackProvider):
        self.ivs_client = ivs_client
        self.playback_provider = playback_provider

    async def create_concert_and_channel(self, data: ConcertCreateRequest, user: User) -> Concert:
        """
        [Admin] 콘서트 생성 및 AWS IVS 채널 자동 발급
        """
        # 권한 체크
        StreamPermission.must_be_admin(user)

        # Concert 생성
        # channel_config는 IVS 설정용이므로 DB 모델 생성시에는 제외
        concert_dict = data.model_dump(exclude={"channel_config", "artist_ids"})
        concert = await Concert.create(**concert_dict)

        # 아티스트 매핑 생성
        if data.artist_ids:
            for artist_id in data.artist_ids:
                await ConcertArtist.create(concert=concert, artist_id=artist_id)

        # IVS 채널 생성 호출
        config = data.channel_config
        is_private = concert.access_level != AccessLevel.PUBLIC  # 비공개

        ivs_res = self.ivs_client.create_channel(
            name=f"concert_{concert.id}",
            latency_mode=config.latency_mode.value,
            channel_type=config.channel_type.value,
            authorized=is_private,
        )

        # StreamChannel(IVS 정보) 저장 및 스트림 키 암호화
        channel = await StreamChannel.create(
            concert=concert,
            type=config.channel_type,
            latency_mode=config.latency_mode,
            channel_arn=ivs_res["channel"]["arn"],
            ingest_endpoint=ivs_res["channel"]["ingestEndpoint"],
            playback_url=ivs_res["channel"]["playbackUrl"],
            is_private=is_private,
        )

        # 모델 내부의 Fernet 암호화 로직 호출
        channel.set_stream_key(ivs_res["streamKey"]["value"])
        await channel.save()

        return concert

    async def get_viewing_credentials(self, concert_id: int, user: User) -> dict[str, Any]:
        """
        [User] 시청 권한 확인 및 재생/채팅 토큰 발급
        """
        concert = await Concert.get(id=concert_id).prefetch_related("stream_channel")

        # 유저 권한 증명
        await StreamPermission.verify_playback_access(user, concert)

        channel: StreamChannel = concert.stream_channel
        playback_url: str = channel.playback_url

        # 비공개 채널이면 토큰 서명
        if channel.is_private:
            token = self.playback_provider.sign_playback_token(
                channel_arn=channel.channel_arn, viewer_id=str(user.id)
            )
            playback_url = f"{playback_url}?token={token}"

        # 내부 세션 토큰
        internal_tokens = self.playback_provider.sign_internal_tokens(
            user_id=str(user.id), stream_id=str(concert.id)
        )

        return {
            "playback_url": playback_url,
            "access_token": internal_tokens["access_token"],
            "refresh_token": internal_tokens["refresh_token"],
        }
