from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.streams.client.service import StreamUserService
from app.domains.streams.models import (
    ConcertSession,
    StreamChannel,
)


class TestStreamService:
    @pytest.fixture
    def mock_ivs_client(self):
        client = MagicMock()
        client.create_channel.return_value = {
            "channel": {
                "arn": "arn:aws:ivs:region:account:channel/test-channel",
                "ingestEndpoint": "rtmps://test.ingest.net/app/",
                "playbackUrl": "https://test.playback.net/index.m3u8",
            },
            "streamKey": {"value": "sk_test_12345"},
        }
        return client

    @pytest.mark.asyncio
    async def test_user_service_viewing_flow(self):
        """User 시청 권한 및 토큰 발급 로직 검증"""
        mock_pb = MagicMock()
        mock_pb.sign_playback_token.return_value = "token_abc"
        mock_pb.sign_internal_tokens.return_value = {"access_token": "at", "refresh_token": "rt"}

        service = StreamUserService(ivs_client=MagicMock(), playback_provider=mock_pb)
        mock_user = MagicMock(id=1)

        # 비공개 채널용 Mock
        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.id = 100
        mock_channel.is_private = True
        mock_channel.channel_arn = "arn:ivs:private"
        mock_channel.playback_url = "https://play.m3u8"

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = mock_channel

        with (
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
            patch(
                "app.domains.streams.permissions.StreamPermission.verify_playback_access",
                new_callable=AsyncMock,
            ),
        ):
            # Prefetch 결과 설정
            mock_get.return_value.prefetch_related = AsyncMock(return_value=mock_session)

            # 실행 및 검증
            res = await service.get_viewing_credentials(10, mock_user)
            assert "token=token_abc" in res["playback_url"]
            assert res["stream_id"] == 100

            # 공개 채널 분기 테스트 (is_private=False)
            mock_channel.is_private = False
            res_public = await service.get_viewing_credentials(10, mock_user)
            assert "token=" not in res_public["playback_url"]

    @pytest.mark.asyncio
    async def test_user_service_refresh_tokens(self):
        """User 시청 세션 토큰 갱신 테스트"""

        # Mock PlaybackProvider 설정
        mock_pb = MagicMock()
        mock_pb.rotate_tokens.return_value = {"access_token": "new_at", "refresh_token": "new_rt"}
        mock_pb.sign_playback_token.return_value = "new_token"

        # 테스트 대상 서비스 생성
        service = StreamUserService(ivs_client=MagicMock(), playback_provider=mock_pb)
        mock_user = MagicMock(id=1)

        # 비공개 채널용 StreamChannel Mock
        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.id = 101
        mock_channel.is_private = True
        mock_channel.channel_arn = "arn:ivs:private"
        mock_channel.playback_url = "https://play.m3u8"

        # 세션에 채널 연결
        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = mock_channel

        # ConcertSession.get() + prefetch_related Mock
        with (
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
            patch(
                "app.domains.streams.permissions.StreamPermission.verify_playback_access",
                new_callable=AsyncMock,
            ),
        ):
            mock_get.return_value.prefetch_related = AsyncMock(return_value=mock_session)

            # 실제 테스트 실행
            res = await service.refresh_viewing_session(10, mock_user, "old_rt")

            # 검증: 토큰 갱신 결과 확인
            assert res["access_token"] == "new_at"
            assert res["refresh_token"] == "new_rt"

            # 검증: 비공개 채널 URL에 서명 토큰 포함
            assert "token=new_token" in res["playback_url"]
