from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_admin_user
from app.domains.concerts.models import Concert
from app.domains.streams.models import AccessLevel, ChannelType, LatencyMode, StreamStatus
from app.main import app


class TestStreamRouter:
    @pytest.fixture
    async def client(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    @pytest.fixture
    def mock_admin_user(self):
        """관리자 권한"""
        user = MagicMock()
        user.id = 1
        user.is_admin = True
        return user

    @pytest.fixture
    def mock_regular_user(self):
        """일반 사용자 권한"""
        user = MagicMock()
        user.id = 2
        user.is_admin = False
        return user

    @pytest.mark.asyncio
    async def test_admin_router_success_flow(self, client, mock_admin_user):
        """관리자 권한으로 콘서트 생성 → 세션 생성 성공하는지 검증"""

        async def override_get_current_user():
            return mock_admin_user

        app.dependency_overrides[get_admin_user] = override_get_current_user

        try:
            with (
                patch(
                    "app.domains.concerts.service.ConcertAdminService.create_concert",
                    new_callable=AsyncMock,
                ) as mock_create_concert,
                patch(
                    "app.domains.streams.admin.service.StreamAdminService.create_session_with_infrastructure",
                    new_callable=AsyncMock,
                ) as mock_create_session,
            ):
                # concert mock
                mock_concert = MagicMock(spec=Concert)
                mock_concert.id = 1
                mock_concert.title = "Test Concert"
                mock_concert.description = "Test Description"
                mock_concert.category = "K-POP"
                mock_concert.thumbnail_url = None
                mock_concert.created_at = datetime.now()
                mock_create_concert.return_value = mock_concert

                # create concert
                res = await client.post(
                    "/api/v1/admin/concerts",
                    json={
                        "title": "Test Concert",
                        "description": "Test Description",
                        "category": "K-POP",
                    },
                )

                assert res.status_code == 201
                assert res.json()["title"] == "Test Concert"

                # session mock
                from app.domains.streams.admin.schemas import (
                    IVSChannelSummary,
                    SessionResponse,
                )

                mock_create_session.return_value = SessionResponse(
                    id=10,
                    session_name="Session 1",
                    access_level=AccessLevel.PUBLIC,
                    start_at=datetime.now(),
                    status=StreamStatus.READY,
                    channel=IVSChannelSummary(
                        arn="arn:test",
                        ingest_endpoint="rtmps://test",
                        playback_url="https://test.m3u8",
                        latency_mode=LatencyMode.LOW,
                        type=ChannelType.STANDARD,
                    ),
                    value="sk_test",
                )

                # create session
                res = await client.post(
                    "/api/v1/admin/streams/concerts/1/sessions",
                    json={
                        "session_name": "Session 1",
                        "access_level": "PUBLIC",
                        "start_at": datetime.now().isoformat(),
                        "channel_config": {
                            "latency_mode": "LOW",
                            "channel_type": "STANDARD",
                        },
                        "artist_ids": [1, 2],
                    },
                )

                assert res.status_code == 201
                assert res.json()["value"] == "sk_test"

        finally:
            app.dependency_overrides.clear()

    class TestStreamRouterExtended:
        """Router 커버리지 향상을 위한 추가 테스트"""

        @pytest.fixture
        async def client(self):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                yield ac

        @pytest.fixture
        def mock_admin_user(self):
            user = MagicMock()
            user.id = 1
            user.is_admin = True
            return user

        @pytest.mark.asyncio
        async def test_delete_concert_session_success(self, client, mock_admin_user):
            """세션 삭제 엔드포인트 성공 케이스"""
            app.dependency_overrides[get_admin_user] = lambda: mock_admin_user

            try:
                with patch(
                    "app.domains.streams.admin.service.StreamAdminService.delete_session_with_infrastructure",
                    new_callable=AsyncMock,
                ) as mock_delete:
                    mock_delete.return_value = None

                    res = await client.delete("/api/v1/admin/streams/sessions/1")
                    assert res.status_code == 204
                    mock_delete.assert_called_once()

            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_rotate_stream_key_success(self, client, mock_admin_user):
            """스트림 키 재발급 엔드포인트 성공 케이스"""
            app.dependency_overrides[get_admin_user] = lambda: mock_admin_user

            try:
                with patch(
                    "app.domains.streams.admin.service.StreamAdminService.rotate_stream_key",
                    new_callable=AsyncMock,
                ) as mock_rotate:
                    mock_rotate.return_value = "new_sk_12345"

                    res = await client.post("/api/v1/admin/streams/sessions/1/rotate-key")
                    assert res.status_code == 200
                    assert res.json()["value"] == "new_sk_12345"
                    assert "재발급" in res.json()["message"]

            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_stop_live_stream_success(self, client, mock_admin_user):
            """라이브 방송 강제 종료 엔드포인트 성공 케이스"""
            app.dependency_overrides[get_admin_user] = lambda: mock_admin_user

            try:
                with patch(
                    "app.domains.streams.admin.service.StreamAdminService.stop_stream_session",
                    new_callable=AsyncMock,
                ) as mock_stop:
                    mock_stop.return_value = None

                    res = await client.post("/api/v1/admin/streams/sessions/1/stop")
                    assert res.status_code == 204

            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_get_session_ingest_data_success(self, client, mock_admin_user):
            """송출 정보 조회 엔드포인트 성공 케이스"""
            app.dependency_overrides[get_admin_user] = lambda: mock_admin_user

            try:
                from app.domains.streams.admin.schemas import (
                    StreamIngestInfo,
                    StreamIngestResponse,
                    StreamLiveMetrics,
                )

                mock_response = StreamIngestResponse(
                    session_id=1,
                    is_live=True,
                    concert_title="Test Concert",
                    session_name="Test Session",
                    ingest_info=StreamIngestInfo(
                        ingest_endpoint="rtmps://test.com",
                        value="sk_test",
                    ),
                    playback_url="https://test.m3u8",
                    live_metrics=StreamLiveMetrics(
                        health="HEALTHY",
                        viewer_count=100,
                        start_time=datetime.now(),
                        state="LIVE",
                    ),
                )

                with patch(
                    "app.domains.streams.admin.service.StreamAdminService.get_stream_ingest_info",
                    new_callable=AsyncMock,
                ) as mock_ingest:
                    mock_ingest.return_value = mock_response

                    res = await client.get("/api/v1/admin/streams/sessions/1/ingest")
                    assert res.status_code == 200
                    data = res.json()
                    assert data["isLive"] is True
                    assert data["liveMetrics"]["viewerCount"] == 100

            finally:
                app.dependency_overrides.clear()
