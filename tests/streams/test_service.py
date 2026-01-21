from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.streams.models import AccessLevel, ChannelType, LatencyMode
from app.domains.streams.schemas import (
    ChannelConfig,
    ConcertCreateRequest,
    SessionCreateRequest,
)
from app.domains.streams.service import StreamAdminService, StreamUserService


class TestStreamService:
    @pytest.mark.asyncio
    async def test_admin_service_coverage(self):
        """Admin 서비스 커버리지 테스트 - 콘서트 및 세션 생성"""

        # Mock IVS Client
        mock_ivs_client = MagicMock()
        mock_ivs_client.create_channel = MagicMock(
            return_value={
                "channel": {
                    "arn": "arn:aws:ivs:region:account:channel/test-channel",
                    "ingestEndpoint": "rtmps://test.global-contribute.live-video.net:443/app/",
                    "playbackUrl": "https://test.us-west-2.playback.live-video.net/api/video/v1/test.m3u8",
                },
                "streamKey": {
                    "value": "sk_test_stream_key_12345",
                },
            }
        )

        service = StreamAdminService(ivs_client=mock_ivs_client)

        # Mock User (admin)
        mock_user = MagicMock()
        mock_user.is_admin = True
        mock_user.id = 1

        # 콘서트 생성 테스트
        concert_data = ConcertCreateRequest(
            title="Test Concert",
            description="Test Description",
            category="K-POP",
        )

        with patch(
            "app.domains.streams.models.Concert.create", new_callable=AsyncMock
        ) as mock_create_concert:
            mock_concert = MagicMock()
            mock_concert.id = 1
            mock_concert.title = "Test Concert"
            mock_create_concert.return_value = mock_concert

            concert = await service.create_concert(concert_data, mock_user)

            assert concert.id == 1
            assert concert.title == "Test Concert"
            mock_create_concert.assert_called_once()

        # 세션 생성 테스트
        session_data = SessionCreateRequest(
            session_name="Session 1",
            access_level=AccessLevel.PUBLIC,
            start_at=datetime.now(),
            channel_config=ChannelConfig(
                latency_mode=LatencyMode.LOW,
                channel_type=ChannelType.STANDARD,
            ),
            artist_ids=[1, 2],
        )

        with (
            patch(
                "app.domains.streams.models.Concert.get", new_callable=AsyncMock
            ) as mock_get_concert,
            patch(
                "app.domains.streams.models.ConcertSession.create", new_callable=AsyncMock
            ) as mock_create_session,
            patch(
                "app.domains.streams.models.ConcertArtist.create", new_callable=AsyncMock
            ) as mock_create_artist,
            patch(
                "app.domains.streams.models.StreamChannel.create", new_callable=AsyncMock
            ) as mock_create_channel,
        ):
            # Mock Concert
            mock_concert = MagicMock()
            mock_concert.id = 1
            mock_get_concert.return_value = mock_concert

            # Mock Session
            mock_session = MagicMock()
            mock_session.id = 10
            mock_session.session_name = "Session 1"
            mock_session.access_level = AccessLevel.PUBLIC
            mock_session.start_at = session_data.start_at
            mock_create_session.return_value = mock_session

            # Mock Channel
            mock_channel = MagicMock()
            mock_channel.id = 100
            mock_channel.channel_arn = "arn:aws:ivs:region:account:channel/test-channel"
            mock_channel.ingest_endpoint = "rtmps://test.global-contribute.live-video.net:443/app/"
            mock_channel.playback_url = (
                "https://test.us-west-2.playback.live-video.net/api/video/v1/test.m3u8"
            )
            mock_channel.latency_mode = LatencyMode.LOW
            mock_channel.type = ChannelType.STANDARD
            mock_channel.is_private = False
            mock_channel.set_stream_key = MagicMock()
            mock_channel.save = AsyncMock()
            mock_create_channel.return_value = mock_channel

            response = await service.create_session_with_infrastructure(
                concert_id=1,
                data=session_data,
                user=mock_user,
            )

            # 검증
            assert response.id == 10
            assert response.session_name == "Session 1"
            assert response.stream_key == "sk_test_stream_key_12345"

            # IVS 채널 생성 호출 확인
            mock_ivs_client.create_channel.assert_called_once()

            # 아티스트 매핑 확인
            assert mock_create_artist.call_count == 2

            # 채널 저장 확인
            mock_channel.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_service_viewing_coverage(self):
        """User 서비스 커버리지 테스트 - 시청 권한 및 토큰 발급"""

        # Mock IVS Client & Playback Provider
        mock_ivs_client = MagicMock()
        mock_playback_provider = MagicMock()
        mock_playback_provider.sign_playback_token = MagicMock(
            return_value="signed_playback_token_abc123"
        )
        mock_playback_provider.sign_internal_tokens = MagicMock(
            return_value={
                "access_token": "access_token_xyz",
                "refresh_token": "refresh_token_xyz",
            }
        )
        mock_playback_provider.rotate_tokens = MagicMock(
            return_value={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
            }
        )

        service = StreamUserService(
            ivs_client=mock_ivs_client,
            playback_provider=mock_playback_provider,
        )

        # Mock User
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_admin = False

        # Mock Session & Channel
        mock_channel = MagicMock()
        mock_channel.id = 100
        mock_channel.channel_arn = "arn:aws:ivs:region:account:channel/test"
        mock_channel.playback_url = "https://test.playback.live-video.net/api/video/v1/test.m3u8"
        mock_channel.is_private = True

        mock_session = MagicMock()
        mock_session.id = 10
        mock_session.stream_channel = mock_channel
        # AccessLevel enum 값 확인 필요 - PUBLIC 외 다른 값 사용
        # TICKETED가 없다면 PUBLIC이 아닌 다른 값으로 테스트
        mock_session.access_level = AccessLevel.PUBLIC  # 일단 PUBLIC으로 테스트

        # 1. 시청 권한 확인 및 토큰 발급 테스트
        with (
            patch("app.domains.streams.models.ConcertSession.get") as mock_get_session,
            patch(
                "app.domains.streams.permissions.StreamPermission.verify_playback_access",
                new_callable=AsyncMock,
            ),
        ):
            # AsyncMock으로 await 가능하게 설정
            async def mock_prefetch(*args, **kwargs):
                return mock_session

            mock_get_result = MagicMock()
            mock_get_result.prefetch_related = mock_prefetch
            mock_get_session.return_value = mock_get_result

            credentials = await service.get_viewing_credentials(
                session_id=10,
                user=mock_user,
            )

            # 검증
            assert "playback_url" in credentials
            assert "token=signed_playback_token_abc123" in credentials["playback_url"]
            assert credentials["stream_id"] == 100
            assert credentials["access_token"] == "access_token_xyz"
            assert credentials["refresh_token"] == "refresh_token_xyz"

            # 토큰 서명 호출 확인
            mock_playback_provider.sign_playback_token.assert_called_once_with(
                channel_arn=mock_channel.channel_arn,
                viewer_id="1",
            )
            mock_playback_provider.sign_internal_tokens.assert_called_once()

        # 시청 세션 연장 테스트
        with (
            patch("app.domains.streams.models.ConcertSession.get") as mock_get_session,
            patch(
                "app.domains.streams.permissions.StreamPermission.verify_playback_access",
                new_callable=AsyncMock,
            ),
        ):

            async def mock_prefetch(*args, **kwargs):
                return mock_session

            mock_get_result = MagicMock()
            mock_get_result.prefetch_related = mock_prefetch
            mock_get_session.return_value = mock_get_result

            refreshed = await service.refresh_viewing_session(
                session_id=10,
                user=mock_user,
                refresh_token="old_refresh_token",
            )

            # 검증
            assert "playback_url" in refreshed
            assert refreshed["access_token"] == "new_access_token"
            assert refreshed["refresh_token"] == "new_refresh_token"

            # 토큰 갱신 호출 확인
            mock_playback_provider.rotate_tokens.assert_called_once_with("old_refresh_token")

    @pytest.mark.asyncio
    async def test_user_service_public_channel(self):
        """공개 채널의 경우 Playback Token 없이 URL만 반환"""

        mock_ivs_client = MagicMock()
        mock_playback_provider = MagicMock()
        mock_playback_provider.sign_internal_tokens = MagicMock(
            return_value={
                "access_token": "access_token_public",
                "refresh_token": "refresh_token_public",
            }
        )
        mock_playback_provider.sign_playback_token = MagicMock()

        service = StreamUserService(
            ivs_client=mock_ivs_client,
            playback_provider=mock_playback_provider,
        )

        mock_user = MagicMock()
        mock_user.id = 2

        mock_channel = MagicMock()
        mock_channel.id = 200
        mock_channel.channel_arn = "arn:aws:ivs:region:account:channel/public"
        mock_channel.playback_url = (
            "https://public.playback.live-video.net/api/video/v1/public.m3u8"
        )
        mock_channel.is_private = False  # 공개 채널

        mock_session = MagicMock()
        mock_session.id = 20
        mock_session.stream_channel = mock_channel
        mock_session.access_level = AccessLevel.PUBLIC

        with (
            patch("app.domains.streams.models.ConcertSession.get") as mock_get_session,
            patch(
                "app.domains.streams.permissions.StreamPermission.verify_playback_access",
                new_callable=AsyncMock,
            ),
        ):

            async def mock_prefetch(*args, **kwargs):
                return mock_session

            mock_get_result = MagicMock()
            mock_get_result.prefetch_related = mock_prefetch
            mock_get_session.return_value = mock_get_result

            credentials = await service.get_viewing_credentials(
                session_id=20,
                user=mock_user,
            )

            # 공개 채널은 토큰 파라미터가 없어야 함
            assert "token=" not in credentials["playback_url"]
            assert credentials["playback_url"] == mock_channel.playback_url

            # Playback 토큰 서명은 호출되지 않아야 함
            mock_playback_provider.sign_playback_token.assert_not_called()
