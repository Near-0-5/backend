from typing import Any

from app.domains.streams.models import (
    ConcertSession,
    StreamChannel,
)
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
