from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
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
    async def test_user_router_get_credentials(self, client, mock_regular_user):
        """일반 사용자가 스트림 세션에 대한 시청 자격 및 토큰을 정상적으로 발급받는지 검증"""

        async def override_get_current_user():
            return mock_regular_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with patch(
                "app.domains.streams.client.service.StreamUserService.get_viewing_credentials",
                new_callable=AsyncMock,
            ) as mock_get_credentials:
                mock_get_credentials.return_value = {
                    "playback_url": "https://test.m3u8",
                    "stream_id": 100,
                    "access_token": "access",
                    "refresh_token": "refresh",
                }

                res = await client.get("/api/v1/streams/sessions/10/credentials")

                assert res.status_code == 200
                assert res.json()["stream_id"] == 100

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_user_router_refresh_session(self, client, mock_regular_user):
        """일반 사용자가 기존 refresh token으로 시청 세션 연장, 새 토큰 발급받는지 검증"""

        async def override_get_current_user():
            return mock_regular_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with patch(
                "app.domains.streams.client.service.StreamUserService.refresh_viewing_session",
                new_callable=AsyncMock,
            ) as mock_refresh:
                mock_refresh.return_value = {
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "playback_url": "https://test.m3u8",
                }

                res = await client.post(
                    "/api/v1/streams/sessions/10/refresh",
                    json={"refresh_token": "old"},
                )

                assert res.status_code == 200

                mock_refresh.assert_called_once_with(
                    10,
                    mock_regular_user,
                    "old",
                )

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, client, mock_admin_user):
        """validation 에러: 422"""

        async def override_get_current_user():
            return mock_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            # missing title
            res = await client.post(
                "/api/v1/admin/streams/concerts",
                json={"description": "missing title"},
            )
            assert res.status_code == 422

            # invalid enum
            res = await client.post(
                "/api/v1/admin/streams/concerts/1/sessions",
                json={
                    "session_name": "Session",
                    "access_level": "INVALID",
                    "start_at": datetime.now().isoformat(),
                    "channel_config": {
                        "latency_mode": "LOW",
                        "channel_type": "STANDARD",
                    },
                },
            )
            assert res.status_code == 422

        finally:
            app.dependency_overrides.clear()
