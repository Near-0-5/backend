from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.domains.streams.admin.schemas import (
    ChannelConfig,
    SessionCreateRequest,
)
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.models import (
    AccessLevel,
    ChannelType,
    ConcertSession,
    LatencyMode,
    StreamChannel,
    StreamStatus,
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
                type=ChannelType.STANDARD,
            ),
            artist_ids=[1],
        )

        with (
            patch("app.domains.streams.models.Concert.get", new_callable=AsyncMock),
            patch(
                "app.domains.streams.models.ConcertSession.create", new_callable=AsyncMock
            ) as mock_sess_create,
            patch(
                "app.domains.streams.admin.service.Artist.filter", new_callable=AsyncMock
            ) as mock_art_filter,
            patch("app.domains.streams.models.ConcertArtist.create", new_callable=AsyncMock),
            patch(
                "app.domains.streams.admin.service.StreamChannel", spec=StreamChannel
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
    async def test_get_stream_ingest_info_success_live(self, mock_ivs_client):
        """방송 중일 때 송출 정보 조회 및 DB 상태 동기화 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        # Mock 데이터 설정 (AWS IVS)
        mock_ivs_client.get_stream_health.return_value = {
            "stream": {
                "health": "HEALTHY",
                "viewerCount": 1500,
                "startTime": datetime.now(),
                "state": "LIVE",
            }
        }

        # DB 모델 Mocking
        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.channel_arn = "arn:aws:ivs:test"
        mock_channel.ingest_endpoint = "rtmps://test-ingest.com"
        mock_channel.playback_url = "https://test-play.com"
        mock_channel.get_stream_key.return_value = "decrypted_sk_123"

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.id = 4
        mock_session.status = "READY"
        mock_session.stream_channel = mock_channel
        mock_session.concert.title = "Test Concert"
        mock_session.save = AsyncMock()

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
        ):
            # get()은 즉시 mock_query를 반환 (비동기 아님)
            mock_query = MagicMock()

            # prefetch_related를 AsyncMock으로 설정하여 await가 가능하게 함
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)

            # ConcertSession.get()이 호출되면 mock_query를 반환
            mock_get.return_value = mock_query

            # 실행
            response = await service.get_stream_ingest_info(session_id=4, user=mock_user)

            # 검증
            assert response.is_live is True
            assert response.live_metrics.viewer_count == 1500
            assert mock_session.status == "LIVE"
            mock_session.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stream_ingest_info_no_channel(self, mock_ivs_client):
        """세션에 IVS 채널이 연결되어 있지 않은 경우 404 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = None

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get.return_value = mock_query

            with pytest.raises(HTTPException) as exc:
                await service.get_stream_ingest_info(1, mock_user)

            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_stream_ingest_info_permission_denied(self, mock_ivs_client):
        """관리자 권한이 없을 때 예외 발생 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=False)  # 일반 유저

        with patch(
            "app.domains.streams.admin.service.StreamPermission.must_be_admin",
            side_effect=HTTPException(status_code=403, detail="권한 없음"),
        ):
            with pytest.raises(HTTPException) as exc:
                await service.get_stream_ingest_info(1, mock_user)

            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rotate_stream_key_success(self, mock_ivs_client):
        """스트림 키 재발급 로직 검증 (기존 키 삭제 후 재생성)"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        # Mock 설정
        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.channel_arn = "arn:aws:ivs:test"
        mock_channel.save = AsyncMock()

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = mock_channel

        # list_all_stream_keys 반환값 설정
        mock_ivs_client.list_all_stream_keys.return_value = [{"arn": "old_key_arn"}]
        mock_ivs_client.create_stream_key.return_value = {"streamKey": {"value": "new_secret_key"}}

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get.return_value = mock_query

            # 실행
            new_key = await service.rotate_stream_key(session_id=1, user=mock_user)

            # 검증
            assert new_key == "new_secret_key"
            mock_ivs_client.delete_stream_key.assert_called_with("old_key_arn")
            mock_channel.set_stream_key.assert_called_with("new_secret_key")
            mock_channel.save.assert_called_once_with(update_fields=["stream_key_encrypted"])

    @pytest.mark.asyncio
    async def test_delete_session_with_infrastructure_success(self, mock_ivs_client):
        """세션 및 IVS 인프라 삭제 로직 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.channel_arn = "arn:aws:ivs:to-delete"

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = mock_channel
        mock_session.delete = AsyncMock()

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get_or_none") as mock_get_none,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get_none.return_value = mock_query

            # 실행
            await service.delete_session_with_infrastructure(session_id=1, user=mock_user)

            # 검증
            mock_ivs_client.delete_channel.assert_called_with("arn:aws:ivs:to-delete")
            mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stream_session_success(self, mock_ivs_client):
        """라이브 강제 중단 및 상태 변경 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        mock_channel = MagicMock(spec=StreamChannel)
        mock_channel.channel_arn = "arn:aws:ivs:live-arn"

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = mock_channel
        mock_session.save = AsyncMock()

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get.return_value = mock_query

            # 실행
            await service.stop_stream_session(session_id=1, user=mock_user)

            # 검증
            mock_ivs_client.stop_stream.assert_called_with("arn:aws:ivs:live-arn")
            assert mock_session.status == StreamStatus.ENDED
            mock_session.save.assert_called_once_with(update_fields=["status"])

    @pytest.mark.asyncio
    async def test_create_session_artist_not_found(self, mock_ivs_client):
        """존재하지 않는 아티스트 ID 요청 시 400 에러 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        session_data = SessionCreateRequest(
            session_name="Session 1",
            access_level=AccessLevel.PUBLIC,
            start_at=datetime.now(),
            channel_config=ChannelConfig(latency_mode=LatencyMode.LOW, type=ChannelType.STANDARD),
            artist_ids=[1, 999],  # 999는 존재하지 않음
        )

        with (
            patch("app.domains.streams.models.Concert.get", new_callable=AsyncMock),
            patch("app.domains.streams.models.ConcertSession.create", new_callable=AsyncMock),
            patch(
                "app.domains.streams.admin.service.Artist.filter", new_callable=AsyncMock
            ) as mock_art_filter,
        ):
            # DB에는 아티스트 1명만 있다고 가정
            mock_art_filter.return_value = [MagicMock(id=1)]

            with pytest.raises(HTTPException) as exc:
                await service.create_session_with_infrastructure(1, session_data, mock_user)

            assert exc.value.status_code == 400
            assert "존재하지 않는 아티스트" in exc.value.detail

    @pytest.mark.asyncio
    async def test_delete_session_aws_failure_continues(self, mock_ivs_client):
        """AWS 채널 삭제 실패 시에도 DB 삭제는 진행되는지(Warning 로그) 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        # AWS 삭제 시 에러 발생 시뮬레이션
        mock_ivs_client.delete_channel.side_effect = Exception("AWS Delete Failed")

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = MagicMock(channel_arn="arn:aws:ivs:error")
        mock_session.delete = AsyncMock()

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get_or_none") as mock_get_none,
            patch("app.domains.streams.admin.service.logger") as mock_logger,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get_none.return_value = mock_query

            # 실행
            await service.delete_session_with_infrastructure(1, mock_user)

            # 검증: AWS 에러가 났지만 DB 삭제는 호출되어야 함
            mock_logger.warning.assert_called()
            mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stream_aws_failure_continues(self, mock_ivs_client):
        """방송 중단 시 AWS 호출 에러가 나도 DB 상태는 변경되는지 검증"""
        service = StreamAdminService(ivs_client=mock_ivs_client)
        mock_user = MagicMock(is_admin=True)

        mock_ivs_client.stop_stream.side_effect = Exception("Already Stopped")

        mock_session = MagicMock(spec=ConcertSession)
        mock_session.stream_channel = MagicMock(channel_arn="arn:aws:ivs:live")
        mock_session.save = AsyncMock()

        with (
            patch("app.domains.streams.admin.service.StreamPermission.must_be_admin"),
            patch("app.domains.streams.models.ConcertSession.get") as mock_get,
            patch("app.domains.streams.admin.service.logger") as mock_logger,
        ):
            mock_query = MagicMock()
            mock_query.prefetch_related = AsyncMock(return_value=mock_session)
            mock_get.return_value = mock_query

            # 실행
            await service.stop_stream_session(1, mock_user)

            # 검증: 에러 로그가 남고 상태는 ENDED로 바뀌어야 함
            mock_logger.warning.assert_called()
            assert mock_session.status == StreamStatus.ENDED
            mock_session.save.assert_called_once()
