from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

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
async def test_kakao_callback_endpoint(mocker):
    """카카오 콜백 시 프론트엔드로 리다이렉트되는지 확인"""
    # 1. 서비스 로직 모킹
    mock_service = mocker.patch(
        "app.domains.auth.router.auth_service.process_kakao_login", new_callable=AsyncMock
    )
    mock_service.return_value = TokenResponse(
        access_token="test_token",
        refresh_token="test_refresh_token",
        token_type="bearer",
        is_new_user=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # follow_redirects=False로 설정해야 302 응답 자체를 검증할 수 있습니다.
        response = await ac.get(
            "/api/v1/auth/kakao/callback?code=mock_code", follow_redirects=False
        )

    # 2. 검증: 302/307 리다이렉트 확인.
    assert response.status_code in [302, 307]

    # 3. 검증: Location 헤더에 토큰과 정보가 포함되어 있는지 확인
    location = response.headers["location"]
    assert "access_token=test_token" in location
    assert "is_new_user=false" in location

    # 4. 검증: 쿠키가 정상적으로 설정되었는지 확인
    set_cookies = response.headers.get_list("set-cookie")
    assert any("refresh_token=test_refresh_token" in c for c in set_cookies)
    assert any("httponly" in c.lower() for c in set_cookies)
