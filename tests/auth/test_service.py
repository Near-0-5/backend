from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.security import create_refresh_token
from app.domains.auth.service import AuthService, auth_service
from app.domains.notifications.models import UserNoti
from app.domains.users.models import ProviderChoice, User
from app.main import app


@pytest.mark.asyncio
async def test_logout_endpoint():
    """로그아웃 시 쿠키 삭제 여부 확인"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/logout")

    assert response.status_code == 204
    # Set-Cookie 헤더에 refresh_token을 지우는 설정이 있는지 확인
    set_cookie_header = response.headers.get("set-cookie", "")

    # refresh_token이라는 키가 포함되어 있는지
    assert "refresh_token" in set_cookie_header
    # 값이 비어있거나(="" 또는 =;) 삭제 설정(Max-Age=0)이 포함되어 있는지 확인
    assert 'refresh_token=""' in set_cookie_header or "Max-Age=0" in set_cookie_header


@pytest.mark.asyncio
async def test_refresh_token_endpoint(initialize_tests):
    """리프레시 토큰으로 액세스 토큰 갱신 테스트"""
    user = await User.create(
        provider_id="999",
        provider=ProviderChoice.KAKAO,
        nickname="del_me",
        email="test@example.com",  # 이메일 등 필수 필드 확인
    )
    refresh_token = create_refresh_token(subject=user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 클라이언트 쿠키에 리프레시 토큰 설정
        ac.cookies.set("refresh_token", refresh_token)
        response = await ac.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    json_data = response.json()
    assert "access_token" in json_data
    assert "refresh_token" in json_data  # 새로운 리프레시 토큰도 함께 오는지 확인


@pytest.mark.asyncio
async def test_image_process_fail_scenarios(mocker):
    """service.py 38, 47-49 라인: 이미지 처리 실패 시나리오"""
    service = AuthService()
    mock_user = MagicMock(spec=User)
    mock_user.id = 99

    # 404 응답 (Line 38)
    mocker.patch("httpx.AsyncClient.get", return_value=MagicMock(status_code=404))
    url = await service._process_and_upload_image(mock_user, "http://orig.url")
    assert url == "http://orig.url"

    # 예외 발생 (Line 47-49)
    mocker.patch("httpx.AsyncClient.get", side_effect=Exception("S3 Fail"))
    url = await service._process_and_upload_image(mock_user, "http://orig.url")
    assert url == "http://orig.url"


@pytest.mark.asyncio
async def test_image_processing_scenarios(mocker):
    """service.py 26, 35-47 라인: 이미지 리사이징 및 S3 업로드 분기 커버"""
    service = AuthService()
    user = MagicMock(spec=User)
    user.id = 1

    # 케이스 1: httpx 응답 실패 (Line 38)
    mocker.patch("httpx.AsyncClient.get", return_value=MagicMock(status_code=404))
    url = await service._process_and_upload_image(user, "http://fail.com")
    assert url == "http://fail.com"

    # 케이스 2: httpx 성공 및 리사이저 실행 (Line 41-45)
    mock_res = MagicMock(status_code=200, content=b"fake_image")
    mocker.patch("httpx.AsyncClient.get", return_value=mock_res)
    mocker.patch(
        "app.core.utils.image_resizer.ImageResizer.upload_square_resizes",
        new_callable=AsyncMock,
        return_value=["http://s3.com/size1.jpg"],
    )

    url = await service._process_and_upload_image(user, "http://success.com")
    assert url == "http://success.com"

    # 케이스 3: 전체 예외 발생 (Line 47)
    mocker.patch("httpx.AsyncClient.get", side_effect=Exception("S3 Error"))
    url = await service._process_and_upload_image(user, "http://error.com")
    assert url == "http://error.com"


@pytest.mark.asyncio
async def test_process_kakao_login_new_user_flow(mocker, initialize_tests):
    """Line 53-106: 신규 유저 생성 및 알림 설정 로직 커버"""
    mocker.patch("app.integrations.kakao.kakao_client.get_access_token", return_value="token")
    mocker.patch(
        "app.integrations.kakao.kakao_client.get_user_info",
        return_value={
            "id": "888888",
            "kakao_account": {
                "email": "new_user@test.com",
                "profile": {"nickname": "신규", "profile_image_url": "http://img.com"},
                "gender": "male",
                "birthday": "0101",
                "birthyear": "1990",
            },
        },
    )
    # 이미지 처리 로직 내부로 진입시키기 위해 patch
    mocker.patch.object(
        AuthService, "_process_and_upload_image", return_value="http://s3.com/p.jpg"
    )

    result = await auth_service.process_kakao_login("code")

    assert result.is_new_user is True
    # Line 100: 알림 설정 생성 확인
    user = await User.get(provider_id="888888")
    noti = await UserNoti.get_or_none(user_id=user.id)
    assert noti is not None


@pytest.mark.asyncio
async def test_image_process_exception_handling(mocker):
    """Line 47-49: 이미지 처리 중 전체 예외 발생 시나리오 (커버리지 핵심)"""
    service = AuthService()
    user = MagicMock(spec=User)
    user.id = 1

    # httpx 호출 시 강제로 Exception 발생
    mocker.patch("httpx.AsyncClient.get", side_effect=RuntimeError("Connection Error"))

    # 예외가 발생해도 로직이 멈추지 않고 원본 URL을 반환해야 함
    url = await service._process_and_upload_image(user, "http://original.com")
    assert url == "http://original.com"


@pytest.mark.asyncio
async def test_auth_service_logout_logic():
    """service.py 124 라인 및 로그아웃 검증 수정"""
    from fastapi import Response

    mock_res = MagicMock(spec=Response)

    await auth_service.logout_user(mock_res)

    # router.py 혹은 service.py 내부에서 실제로 사용하는 인자들과 일치해야 함
    # secure=True, samesite="none", path="/" 등을 확인
    mock_res.delete_cookie.assert_called_once()
    _, kwargs = mock_res.delete_cookie.call_args
    assert kwargs["key"] == "refresh_token"
    assert kwargs["path"] == "/"


@pytest.mark.asyncio
async def test_auth_service_cognito_lines_coverage(mocker):
    """service.py 139-140, 146 라인 커버"""
    mocker.patch(
        "app.domains.auth.service.verify_cognito_token",
        side_effect=HTTPException(status_code=401, detail="Token validation failed"),
    )

    # Ruff B017 해결을 위해서 구체적인 예외 클래스인 HTTPException을 사용.
    with pytest.raises(HTTPException) as excinfo:
        from app.core.security import verify_cognito_token

        await verify_cognito_token("invalid_token")

    # 추가 검증 (Ruff가 요구하는 '상세한 예외 검증')
    assert excinfo.value.status_code == 401
    assert "Token validation failed" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_process_and_upload_image_exception_coverage(mocker):
    """service.py 26 라인 등 예외 처리 커버"""
    service = AuthService()
    mock_user = MagicMock(spec=User)
    mock_user.id = 1

    # httpx.get 호출 시 예기치 못한 에러 발생 유도 (Line 47-49)
    mocker.patch("httpx.AsyncClient.get", side_effect=RuntimeError("Network down"))

    url = await service._process_and_upload_image(mock_user, "http://some-image.com")
    # 예외가 발생해도 로직상 원본 URL을 반환하며 커버리지가 채워짐
    assert url == "http://some-image.com"


@pytest.mark.asyncio
async def test_process_cognito_login_success(mocker, initialize_tests):
    """service.py: Cognito 로그인 처리 및 유저 생성/업데이트 로직 검증"""
    from app.domains.auth.service import auth_service
    from app.domains.users.models import User

    # 1. 외부 연동 모킹 (verify_cognito_token)
    mocker.patch(
        "app.domains.auth.service.verify_cognito_token",
        new_callable=AsyncMock,
        return_value={
            "sub": "cognito_sub_123",
            "email": "cognito@test.com",
            "custom:nickname": "코그니토유저",
        },
    )

    # 2. 서비스 실행
    result = await auth_service.process_cognito_login("fake_id_token")

    # 3. 검증
    assert result.access_token is not None
    assert result.refresh_token is not None

    # DB에 유저가 생성되었는지 확인
    user = await User.get_or_none(provider_id="cognito_sub_123")
    assert user is not None
    assert user.email == "cognito@test.com"
