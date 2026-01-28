from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domains.streams.deps import get_admin_user
from app.domains.streams.models import AccessLevel, StreamStatus
from app.main import app


# Tortoise-ORM 쿼리 체이닝 흉내
class AsyncQueryMock:
    def __init__(self, return_value):
        self.return_value = return_value

    def prefetch_related(self, *args, **kwargs):
        return self

    def select_for_update(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self

    def __await__(self):
        async def _internal():
            return self.return_value

        return _internal().__await__()


@pytest.mark.asyncio
class TestStreamAdminCoverage:
    @pytest.fixture
    async def client(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    def mock_admin_user(self):
        user = MagicMock()
        user.id = 1
        user.is_admin = True
        user.is_superuser = True
        return user

    @pytest.fixture
    def mock_session_data(self):
        session = MagicMock()
        session.id = 1
        session.session_name = "테스트 세션"
        session.access_level = AccessLevel.PUBLIC
        session.status = StreamStatus.READY
        session.start_at = datetime.now(UTC)  # None 대신 실제 객체

        channel = MagicMock()
        channel.channel_arn = "arn:aws:ivs:test"
        channel.ingest_endpoint = "rtmps://ingest.com"
        channel.playback_url = "https://playback.com"
        channel.latency_mode = MagicMock(value="LOW")
        channel.type = MagicMock(value="STANDARD")
        channel.get_stream_key.return_value = "key"
        channel.is_private = False

        session.stream_channel = channel
        concert = MagicMock()
        concert.id = 99
        concert.title = "콘서트"
        concert.category = "K-POP"
        concert.description = "설명"
        concert.thumbnail_url = "old.png"
        concert.thumbnailUrl = "old.png"

        session.concert = concert
        session.save = AsyncMock()
        session.delete = AsyncMock()
        return session

    # 1. [Service 53-77] 썸네일 업로드 로직 격파
    async def test_update_concert_thumbnail_full_logic(
        self, client, mock_admin_user, mock_session_data
    ):
        app.dependency_overrides[get_admin_user] = lambda: mock_admin_user
        mock_concert = mock_session_data.concert
        mock_concert.save = AsyncMock()

        with (
            patch(
                "app.domains.streams.models.Concert.get_or_none",
                new_callable=AsyncMock,
                return_value=mock_concert,
            ),
            patch(
                "app.core.utils.image_resizer.ImageResizer.delete_all_by_id_path",
                new_callable=AsyncMock,
            ),
            patch(
                "app.core.utils.image_resizer.ImageResizer.upload_square_resizes",
                new_callable=AsyncMock,
                return_value={"640": "new.png"},
            ),
        ):
            files = {"thumbnail_file": ("test.jpg", b"data", "image/jpeg")}
            res = await client.patch("/api/v1/admin/streams/concerts/99/thumbnail", files=files)
            assert res.status_code == 200
            assert mock_concert.thumbnail_url == "new.png"

    # 2. [Service 163, 216, 239] 삭제/중단 AWS 예외 로그 처리 격파
    async def test_aws_exception_warning_logs(self, client, mock_admin_user, mock_session_data):
        app.dependency_overrides[get_admin_user] = lambda: mock_admin_user
        query_mock = AsyncQueryMock(mock_session_data)

        # 삭제 시 AWS 에러 발생 (Service 163)
        with (
            patch("app.domains.streams.models.ConcertSession.get_or_none", return_value=query_mock),
            patch(
                "app.integrations.aws_ivs.IVSClient.delete_channel",
                side_effect=Exception("AWS Error"),
            ),
        ):
            res = await client.delete("/api/v1/admin/streams/sessions/1")
            assert res.status_code == 204

        # 중단 시 AWS 에러 발생 (Service 216)
        with (
            patch("app.domains.streams.models.ConcertSession.get", return_value=query_mock),
            patch(
                "app.integrations.aws_ivs.IVSClient.stop_stream", side_effect=Exception("AWS Error")
            ),
        ):
            res = await client.post("/api/v1/admin/streams/sessions/1/stop")
            assert res.status_code == 200

    # 3. [Service 374-378] 아티스트 매핑 업데이트 및 Pydantic 에러 해결
    async def test_update_session_artist_mapping_and_pydantic(
        self, client, mock_admin_user, mock_session_data
    ):
        app.dependency_overrides[get_admin_user] = lambda: mock_admin_user
        query_mock = AsyncQueryMock(mock_session_data)

        from app.domains.streams.admin.schemas import IVSChannelSummary, SessionResponse

        mock_response = SessionResponse(
            id=1,
            session_name="세션",
            access_level=AccessLevel.PUBLIC,
            status=StreamStatus.READY,
            start_at=datetime.now(UTC),  # 👈 여기서 datetime 객체를 줌으로써 ValidationError 해결
            channel=IVSChannelSummary(
                arn="arn",
                ingest_endpoint="ep",
                playback_url="url",
                latency_mode="LOW",
                type="STANDARD",
            ),
        )

        with (
            patch("app.domains.streams.models.ConcertSession.filter", return_value=query_mock),
            patch(
                "app.domains.artists.models.Artist.filter",
                new_callable=AsyncMock,
                return_value=[MagicMock(id=7)],
            ),
            patch("app.domains.streams.models.ConcertArtist.filter") as mock_ca_filter,
            patch("app.domains.streams.models.ConcertArtist.create", new_callable=AsyncMock),
            patch(
                "app.domains.streams.admin.service.StreamAdminService.get_session_admin_detail",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            mock_ca_filter.return_value.delete = AsyncMock()
            # artist_ids를 실어서 374-378 라인을 타게 함
            res = await client.patch("/api/v1/admin/streams/sessions/1", json={"artist_ids": [7]})
            assert res.status_code == 200

    # 4. [Service 411] 라이브 메트릭 계산
    async def test_get_session_ingest_metrics_coverage(
        self, client, mock_admin_user, mock_session_data
    ):
        app.dependency_overrides[get_admin_user] = lambda: mock_admin_user
        query_mock = AsyncQueryMock(mock_session_data)
        mock_health = {
            "stream": {
                "health": "HEALTHY",
                "viewerCount": 5,
                "state": "LIVE",
                "startTime": datetime.now(UTC),
            }
        }

        with (
            patch("app.domains.streams.models.ConcertSession.get", return_value=query_mock),
            patch("app.integrations.aws_ivs.IVSClient.get_stream_health", return_value=mock_health),
        ):
            res = await client.get("/api/v1/admin/streams/sessions/1/ingest")
            assert res.status_code == 200
