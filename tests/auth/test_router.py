from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user_from_refresh_cookie
from app.domains.auth.schemas import TokenResponse
from app.domains.users.models import ProviderChoice, User
from app.main import app


@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_kakao_callback_endpoint(mocker):
    """카카오 콜백 시 JSON 응답과 쿠키가 정상적으로 반환되는지 확인"""
    # 1. 서비스 로직 모킹
    mock_service = mocker.patch(
        "app.domains.auth.router.auth_service.process_cognito_login", new_callable=AsyncMock
    )
    mock_service.return_value = TokenResponse(
        access_token="test_token",
        refresh_token="test_refresh_token",
        token_type="bearer",
        is_new_user=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 이제 리다이렉트가 아니므로 follow_redirects 옵션은 의미가 없지만 유지해도 무방합니다.
        response = await ac.get("/api/v1/auth/cognito/callback?code=mock_code")

    # 2. 검증: 200 OK 확인
    assert response.status_code == 200

    # 3. 검증: 응답 바디(JSON)에 토큰 정보가 포함되어 있는지 확인
    data = response.json()
    assert data["access_token"] == "test_token"
    assert data["is_new_user"] is False
    assert data["token_type"] == "Bearer"

    # 4. 검증: 쿠키가 정상적으로 설정되었는지 확인
    set_cookies = response.headers.get_list("set-cookie")
    assert any("refresh_token=test_refresh_token" in c for c in set_cookies)
    assert any("httponly" in c.lower() for c in set_cookies)


@pytest.mark.asyncio
async def test_kakao_callback_logic(mocker):
    """JSON 응답 및 바디 데이터 구조 검증"""
    mock_token = TokenResponse(
        access_token="at", refresh_token="rt", token_type="bearer", is_new_user=True
    )
    mocker.patch(
        "app.domains.auth.router.auth_service.process_cognito_login",
        new_callable=AsyncMock,
        return_value=mock_token,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/cognito/callback?code=mock")

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "at"
    assert data["is_new_user"] is True
    assert "refresh_token=rt" in response.headers.get("set-cookie")


@pytest.mark.asyncio
async def test_refresh_token_logic(mocker, initialize_tests):
    """router.py 73-94 라인: 리프레시 토큰 발급 전체 로직"""
    user = await User.create(provider_id="ref_1", provider=ProviderChoice.KAKAO, nickname="ref")

    # 의존성 오버라이드 (Line 76)
    app.dependency_overrides[get_current_user_from_refresh_cookie] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.headers.get("set-cookie")

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_login_endpoint_coverage(initialize_tests):
    """router.py 23-38 라인: 개발용 로그인 엔드포인트 커버"""
    user = await User.create(
        provider_id="admin_user", provider=ProviderChoice.KAKAO, nickname="admin"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 정확한 prefix(/api/v1) 사용 확인
        response = await ac.post(f"/api/v1/auth/login-test?user_id={user.id}")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.headers.get("set-cookie")


@pytest.mark.asyncio
async def test_kakao_callback_cookie_logic_coverage(mocker):
    """쿠키의 상세 옵션(Secure, SameSite, HttpOnly) 검증"""
    mock_token = TokenResponse(
        access_token="at", refresh_token="rt", token_type="bearer", is_new_user=True
    )

    mocker.patch(
        "app.domains.auth.router.auth_service.process_cognito_login",
        new_callable=AsyncMock,
        return_value=mock_token,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/cognito/callback?code=fake_code")

    # 1. 상태 코드 확인
    assert response.status_code == 200

    # 2. 쿠키 상세 설정 확인
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "refresh_token=rt" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=none" in set_cookie
    assert "secure" in set_cookie

    # 3. 바디 데이터 확인 (기존 Location 헤더 검증 제거)
    data = response.json()
    assert data["access_token"] == "at"
    assert data["is_new_user"] is True


@pytest.mark.asyncio
async def test_refresh_token_dependency_coverage(mocker, initialize_tests):
    """router.py 73-94 라인: 리프레시 토큰 발급 로직"""
    user = await User.create(
        provider_id="ref_tester", provider=ProviderChoice.KAKAO, nickname="ref"
    )

    # 의존성 주입 오버라이드
    app.dependency_overrides[get_current_user_from_refresh_cookie] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_naver_login_start(ac: AsyncClient):
    """네이버 로그인 시작 시 state 쿠키 생성 확인"""
    # URL 경로를 앱의 prefix(/api/v1)에 맞춰 정확히 기입
    response = await ac.get("/api/v1/auth/login?provider=Naver", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert "naver_state" in response.cookies
    assert "nid.naver.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_naver_callback_success(mocker, ac: AsyncClient):
    """네이버 콜백 성공 및 state 검증 테스트"""
    # 1. state 생성 및 쿠키 설정 시뮬레이션
    state = "test_state_123"
    ac.cookies.set("naver_state", state)

    # 2. 서비스 로직 모킹
    mock_token = AsyncMock()
    mock_token.access_token = "at"
    mock_token.refresh_token = "rt"
    mock_token.is_new_user = False
    mocker.patch(
        "app.domains.auth.router.auth_service.process_naver_login", return_value=mock_token
    )

    # 3. 콜백 호출
    response = await ac.get(f"/api/v1/auth/naver/callback?code=code&state={state}")

    assert response.status_code in [302, 307]
    assert "refresh_token" in response.cookies
    assert response.cookies.get("naver_state") is None  # 검증 후 삭제 확인


@pytest.mark.asyncio
async def test_naver_callback_state_mismatch(ac: AsyncClient):
    """Missing lines 136-165 (state 불일치) 커버"""
    # 1. 클라이언트 쿠키에 잘못된 state 설정
    ac.cookies.set("naver_state", "original_state")

    # 2. 쿼리 파라미터로 다른 state 전송
    response = await ac.get("/api/v1/auth/naver/callback?code=code&state=wrong_state")

    # 3. router.py의 400 raise HTTPException 구문이 실행됨
    assert response.status_code == 400
    assert "비정상적인 접근" in response.text
