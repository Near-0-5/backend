from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.domains.streams.models import (
    AccessLevel,
    ChannelType,
    ConcertSession,
    LatencyMode,
    StreamChannel,
)
from app.domains.streams.schemas import (
    ChannelConfig,
    SessionCreateRequest,
)
from app.domains.streams.service import StreamAdminService, StreamUserService


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
    async def test_admin_service_coverage(self, mock_ivs_client):
        """Admin 세션 생성 및 DB 에러 시 롤백 로직 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        now = datetime.now()
        session_data = SessionCreateRequest(
            session_name="Session 1",
            access_level=AccessLevel.PUBLIC,
            start_at=now,
            channel_config=ChannelConfig(
                latency_mode=LatencyMode.LOW,
                channel_type=ChannelType.STANDARD,
            ),
            artist_ids=[1],
        )

        with (
            patch("app.domains.streams.models.Concert.get", new_callable=AsyncMock),
            patch(
                "app.domains.streams.models.ConcertSession.create", new_callable=AsyncMock
            ) as mock_sess_create,
            patch(
                "app.domains.streams.service.Artist.filter", new_callable=AsyncMock
            ) as mock_art_filter,
            patch("app.domains.streams.models.ConcertArtist.create", new_callable=AsyncMock),
            patch(
                "app.domains.streams.service.StreamChannel", spec=StreamChannel
            ) as mock_chan_class,
        ):
            # ConcertSession Mock 설정
            mock_session = MagicMock(spec=ConcertSession)
            mock_session.id = 10
            mock_session.session_name = "Session 1"
            mock_session.access_level = AccessLevel.PUBLIC
            mock_session.start_at = now
            mock_sess_create.return_value = mock_session

            mock_art_filter.return_value = [MagicMock(id=1)]

            # StreamChannel Mock 설정
            mock_channel_inst = MagicMock(spec=StreamChannel)
            mock_channel_inst.save = AsyncMock()
            mock_channel_inst.channel_arn = "arn:aws:ivs:region:account:channel/test-channel"
            # Response 스키마 생성을 위한 필드들
            mock_channel_inst.ingest_endpoint = "rtmps://test.ingest.net/app/"
            mock_channel_inst.playback_url = "https://test.playback.net/index.m3u8"
            mock_channel_inst.latency_mode = LatencyMode.LOW
            mock_channel_inst.type = ChannelType.STANDARD

            mock_chan_class.return_value = mock_channel_inst

            # 성공 케이스 검증
            response = await service.create_session_with_infrastructure(1, session_data, mock_user)
            assert response.id == 10
            assert response.stream_key == "sk_test_12345"

            # DB 저장 실패 시 롤백(delete_channel) 검증
            mock_channel_inst.save.side_effect = Exception("DB Save Error")
            with pytest.raises(HTTPException) as exc:
                await service.create_session_with_infrastructure(1, session_data, mock_user)

            assert "롤백" in exc.value.detail
            mock_ivs_client.delete_channel.assert_called_with(mock_channel_inst.channel_arn)

    @pytest.mark.asyncio
    async def test_admin_ivs_permission_denied(self, mock_ivs_client):
        """AWS IAM 권한 부족 에러 핸들링"""
        error_res = {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}}
        mock_ivs_client.create_channel.side_effect = ClientError(error_res, "CreateChannel")

        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        with (
            patch("app.domains.streams.models.Concert.get", new_callable=AsyncMock),
            patch("app.domains.streams.models.ConcertSession.create", new_callable=AsyncMock) as m,
        ):
            # session.id가 있어야 IVS 채널 명칭(session-{id}) 생성이 가능함
            mock_sess = MagicMock(spec=ConcertSession)
            mock_sess.id = 99
            mock_sess.access_level = AccessLevel.PUBLIC
            m.return_value = mock_sess

            with pytest.raises(HTTPException) as exc:
                # artist_ids가 비어있어도 로직상 문제없음
                await service.create_session_with_infrastructure(
                    1, MagicMock(artist_ids=[]), mock_user
                )

            assert "AWS 권한 부족" in exc.value.detail

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
