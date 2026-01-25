from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.main import app


@pytest.mark.asyncio
class TestStreamRouter:
    @pytest.fixture
    def mock_user(self):
        user = AsyncMock()
        user.id = 1
        return user

    async def test_get_stream_access_endpoint(self, client, mock_user):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        mock_service = AsyncMock()
        mock_service.get_viewing_credentials.return_value = {"playback_url": "test"}
        app.dependency_overrides[streams_deps.get_stream_user_service] = lambda: mock_service
        try:
            res = await client.get("/api/v1/streams/sessions/1/credentials")
            assert res.status_code == 200
        finally:
            app.dependency_overrides.clear()

    async def test_refresh_stream_session_endpoint(self, client, mock_user):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        mock_service = AsyncMock()
        mock_service.refresh_viewing_session.return_value = {"access_token": "new"}
        app.dependency_overrides[streams_deps.get_stream_user_service] = lambda: mock_service
        try:
            res = await client.post(
                "/api/v1/streams/sessions/1/refresh", json={"refresh_token": "old"}
            )
            assert res.status_code == 200
        finally:
            app.dependency_overrides.clear()

    async def test_list_sessions_router_mapping(self, client, mock_user):
        """GET /sessions 데이터 변환 검증 (커버리지 84-96 라인)"""
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user

        # Mock 구성 (AttributeError 방지)
        mock_session = MagicMock()
        mock_session.id = 10
        mock_session.session_name = "Real Session"
        mock_session.status = "LIVE"
        mock_session.start_at = datetime.now()

        # 중첩된 객체(concert) 속성 설정
        mock_session.concert.title = "Mapped Title"
        mock_session.concert.thumbnail_url = "https://thumb.png"
        mock_session.concert.category = "K-POP"

        # router.py의 s.__dict__ 사용 부분 대응
        mock_session.__dict__ = {
            "id": 10,
            "session_name": "Real Session",
            "status": "LIVE",
            "start_at": mock_session.start_at,
            "concert": mock_session.concert,  # concert 객체도 포함
        }

        mock_service = AsyncMock()
        mock_service.list_sessions.return_value = ([mock_session], 11)
        app.dependency_overrides[streams_deps.get_stream_user_service] = lambda: mock_service

        try:
            res = await client.get("/api/v1/streams/sessions", params={"limit": 5})
            assert res.status_code == 200
            data = res.json()
            assert data["items"][0]["concert_title"] == "Mapped Title"
        finally:
            app.dependency_overrides.clear()

    async def test_list_sessions_validation_error(self, client):
        res = await client.get("/api/v1/streams/sessions", params={"limit": 0})
        assert res.status_code == 422
