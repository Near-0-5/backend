from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.domains.auth.schemas import TokenResponse
from app.main import app


@pytest.mark.asyncio
async def test_kakao_login_redirect():
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/kakao/login", follow_redirects=False)

    assert response.status_code in [302, 307]
    assert "kauth.kakao.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_kakao_callback_endpoint():
    # 실제 카카오를 호출하지 않도록 서비스 로직 모킹
    with patch(
        "app.domains.auth.service.auth_service.process_kakao_login", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = TokenResponse(
            access_token="test_token",
            refresh_token="test_refresh_token",
            token_type="bearer",
            is_new_user=False,
        )

        from httpx import ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/auth/kakao/callback?code=mock_code")

        assert response.status_code == 200
        assert response.json()["access_token"] == "test_token"
