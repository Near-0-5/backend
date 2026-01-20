from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.domains.auth.service import auth_service
from app.main import app


@pytest.mark.asyncio
async def test_process_kakao_login_new_user(mocker):
    # 1. 카카오 클라이언트 모킹
    mocker.patch("app.integrations.kakao.kakao_client.get_access_token", return_value="kakao_token")
    mocker.patch(
        "app.integrations.kakao.kakao_client.get_user_info",
        return_value={
            "id": "12345",
            "kakao_account": {
                "email": "test@test.com",
                "gender": "male",
                "birthyear": "1990",
                "birthday": "0101",
                "profile": {"nickname": "테스터", "profile_image_url": "http://image.com"},
            },
        },
    )

    # 2. DB 모델 모킹
    mock_user = mocker.Mock()
    mock_user.id = 1
    mocker.patch(
        "app.domains.users.models.User.get_or_none", new_callable=AsyncMock, return_value=None
    )
    mocker.patch(
        "app.domains.users.models.User.update_or_create",
        new_callable=AsyncMock,
        return_value=(mock_user, True),
    )
    mocker.patch("app.domains.users.models.User.update_or_create", return_value=(mock_user, True))
    mocker.patch("app.domains.notifications.models.UserNoti.create", new_callable=AsyncMock)

    # 3. 실행
    response = await auth_service.process_kakao_login("some_code")

    # 4. 검증
    assert response.is_new_user is True
    assert response.token_type == "bearer"
    assert response.access_token is not None


@pytest.mark.asyncio
async def test_process_kakao_login_existing_user(mocker):
    """기존 유저 로그인 시나리오 (created=False 분기 커버)"""
    mocker.patch("app.integrations.kakao.kakao_client.get_access_token", return_value="token")
    mocker.patch(
        "app.integrations.kakao.kakao_client.get_user_info",
        return_value={"id": "12345", "kakao_account": {"profile": {"nickname": "기존유저"}}},
    )

    mock_user = mocker.Mock()
    mock_user.id = 1
    # User.get_or_none: 닉네임 중복 체크 통과를 위해 None 반환
    mocker.patch(
        "app.domains.users.models.User.get_or_none", new_callable=AsyncMock, return_value=None
    )
    mocker.patch(
        "app.domains.users.models.User.update_or_create",
        new_callable=AsyncMock,
        return_value=(mock_user, True),
    )
    # update_or_create: created=False 반환 (기존 유저)
    mocker.patch("app.domains.users.models.User.update_or_create", return_value=(mock_user, False))
    # UserNoti.create가 호출되지 않아야 함을 검증하기 위한 스파이
    mock_noti = mocker.patch("app.domains.notifications.models.UserNoti.create")

    response = await auth_service.process_kakao_login("code")

    assert response.is_new_user is False
    assert mock_noti.called is False  # created가 False이므로 알림 생성 패스됨


@pytest.mark.asyncio
async def test_process_kakao_login_nickname_collision_and_female(mocker):
    """닉네임 중복 및 여성 성별 처리 (중복 닉네임 변경 및 gender='F' 분기 커버)"""
    mocker.patch("app.integrations.kakao.kakao_client.get_access_token", return_value="token")
    mocker.patch(
        "app.integrations.kakao.kakao_client.get_user_info",
        return_value={
            "id": "99999",
            "kakao_account": {"gender": "female", "profile": {"nickname": "중복닉네임"}},
        },
    )

    # 1. 닉네임이 이미 존재하는데, provider_id가 다른 경우 (닉네임 뒤에 랜덤값 붙는 로직 실행)
    collision_user = mocker.Mock()
    collision_user.provider_id = "different_id"
    mocker.patch(
        "app.domains.users.models.User.get_or_none",
        new_callable=AsyncMock,
        return_value=collision_user,
    )

    mock_user = mocker.Mock()
    mock_user.id = 2
    mock_update = mocker.patch(
        "app.domains.users.models.User.update_or_create", return_value=(mock_user, True)
    )
    mocker.patch("app.domains.notifications.models.UserNoti.create", new_callable=AsyncMock)

    await auth_service.process_kakao_login("code")

    # 검증: update_or_create에 전달된 닉네임에 랜덤 문자열이 붙었는지 확인
    args, kwargs = mock_update.call_args
    assert "중복닉네임_" in kwargs["defaults"]["nickname"]
    assert kwargs["defaults"]["gender"] == "M" or "F"  # "F"가 매핑되었는지 확인
    assert kwargs["defaults"]["gender"] == "F"


@pytest.mark.asyncio
async def test_process_kakao_login_invalid_birthdate(mocker):
    """잘못된 생일 형식 처리 (ValueError 예외 블록 커버)"""
    mocker.patch("app.integrations.kakao.kakao_client.get_access_token", return_value="token")
    mocker.patch(
        "app.integrations.kakao.kakao_client.get_user_info",
        return_value={
            "id": "123",
            "kakao_account": {
                "birthyear": "1990",
                "birthday": "0230",  # 존재하지 않는 날짜(2월 30일) -> ValueError 발생 유도
            },
        },
    )

    mocker.patch(
        "app.domains.users.models.User.get_or_none", new_callable=AsyncMock, return_value=None
    )
    mock_update = mocker.patch(
        "app.domains.users.models.User.update_or_create", return_value=(mocker.Mock(), True)
    )
    mocker.patch("app.domains.notifications.models.UserNoti.create", new_callable=AsyncMock)

    await auth_service.process_kakao_login("code")

    # 검증: ValueError가 발생하여 birth_date가 None으로 저장되었는지 확인
    args, kwargs = mock_update.call_args
    assert kwargs["defaults"]["birth_date"] is None


@pytest.mark.asyncio
async def test_kakao_login_redirect():
    """/auth/kakao/login 리다이렉트 테스트"""
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/kakao/login", follow_redirects=False)

    assert response.status_code == 307
    assert "kauth.kakao.com" in response.headers["location"]
    assert "client_id=" in response.headers["location"]


@pytest.mark.asyncio
async def test_kakao_callback_endpoint(mocker):
    """/auth/kakao/callback 엔드포인트 테스트"""
    # 서비스 로직 모킹
    mock_service = mocker.patch(
        "app.domains.auth.router.auth_service.process_kakao_login", new_callable=AsyncMock
    )
    mock_service.return_value = {
        "access_token": "fake_jwt",
        "token_type": "bearer",
        "is_new_user": True,
    }

    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/kakao/callback?code=test_code")

    assert response.status_code == 200
    assert response.json()["access_token"] == "fake_jwt"
    mock_service.assert_called_once_with("test_code")
