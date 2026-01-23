from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from app.domains.streams import deps

# --- 기초 서비스 주입 테스트 ---


def test_get_ivs_client():
    client = deps.get_ivs_client()
    assert client is not None
    assert hasattr(client, "create_channel")


def test_get_playback_provider():
    provider = deps.get_playback_provider()
    assert provider is not None
    assert hasattr(provider, "sign_playback_token")


def test_get_stream_admin_service():
    service = deps.get_stream_admin_service()
    assert service is not None
    assert service.ivs_client is not None


def test_get_stream_user_service():
    service = deps.get_stream_user_service()
    assert service is not None
    assert service.ivs_client is not None
    assert service.playback_provider is not None


# --- get_admin_user 인증 흐름 테스트 ---


@pytest.mark.asyncio
async def test_get_admin_user_success_via_header():
    """Access Token(헤더)으로 인증 성공"""
    mock_user = MagicMock()
    mock_user.is_superuser = True

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer valid_token"}
    mock_request.cookies = {}

    with patch(
        "app.domains.streams.deps.get_current_user", new_callable=AsyncMock
    ) as mock_get_current:
        mock_get_current.return_value = mock_user
        result = await deps.get_admin_user(request=mock_request)

        assert result == mock_user
        mock_get_current.assert_called_once()


@pytest.mark.asyncio
async def test_get_admin_user_success_via_cookie():
    """헤더 인증 실패 후 Cookie(Refresh Token)로 인증 성공"""
    mock_user = MagicMock()
    mock_user.is_superuser = True

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer invalid_token"}
    mock_request.cookies = {"refresh_token": "valid_refresh"}

    # get_current_user는 실패(401), 하지만 쿠키 기반 함수는 성공하도록 설정
    with (
        patch(
            "app.domains.streams.deps.get_current_user", side_effect=HTTPException(status_code=401)
        ),
        patch(
            "app.domains.streams.deps.get_current_user_from_refresh_cookie", new_callable=AsyncMock
        ) as mock_get_refresh,
    ):
        mock_get_refresh.return_value = mock_user
        result = await deps.get_admin_user(request=mock_request)

        assert result == mock_user
        mock_get_refresh.assert_called_once_with("valid_refresh")


@pytest.mark.asyncio
async def test_get_admin_user_no_auth_info_error():
    """헤더와 쿠키 모두 인증 정보가 없을 때"""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.cookies = {}

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_admin_user(request=mock_request)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "인증 정보가 없습니다" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_admin_user_forbidden():
    """인증은 성공했으나 관리자 권한(is_superuser)이 없는 경우 (403 에러)"""
    mock_user = MagicMock()
    mock_user.is_superuser = False  # 관리자 아님

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer some_token"}
    mock_request.cookies = {}

    with patch(
        "app.domains.streams.deps.get_current_user", new_callable=AsyncMock
    ) as mock_get_current:
        mock_get_current.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await deps.get_admin_user(request=mock_request)

        # StreamPermission.must_be_admin()에서 발생시키는 403 체크
        assert exc_info.value.status_code == 403
