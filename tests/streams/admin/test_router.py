from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.domains.streams.models import AccessLevel, ChannelType, LatencyMode
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

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with (
                patch(
                    "app.domains.streams.admin.service.StreamAdminService.create_concert",
                    new_callable=AsyncMock,
                ) as mock_create_concert,
                patch(
                    "app.domains.streams.admin.service.StreamAdminService.create_session_with_infrastructure",
                    new_callable=AsyncMock,
                ) as mock_create_session,
            ):
                # concert mock
                mock_concert = MagicMock()
                mock_concert.id = 1
                mock_concert.title = "Test Concert"
                mock_concert.description = "Test Description"
                mock_concert.category = "K-POP"
                mock_concert.created_at = datetime.now()
                mock_create_concert.return_value = mock_concert

                # create concert
                res = await client.post(
                    "/api/v1/admin/streams/concerts",
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
                    channel=IVSChannelSummary(
                        arn="arn:test",
                        ingestEndpoint="rtmps://test",
                        playbackUrl="https://test.m3u8",
                        latencyMode=LatencyMode.LOW,
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
