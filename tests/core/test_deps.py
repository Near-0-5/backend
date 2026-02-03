from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException, status
from fastapi.exceptions import WebSocketException

from app.api.deps import (
    get_current_user,
    get_current_user_by_cognito,
    get_current_user_from_refresh_cookie,
    get_current_user_from_refresh_cookie_ws,
)
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, create_refresh_token
from app.domains.users.models import ProviderChoice, User


@pytest.mark.asyncio
async def test_get_current_user_success(initialize_tests):
    # 1. 테스트용 유저 생성
    user = await User.create(
        provider_id="12345", provider=ProviderChoice.KAKAO, nickname="testuser"
    )
    # 2. 유효한 토큰 생성
    token = create_access_token(subject=user.id)
    auth_creds = MagicMock()
    auth_creds.credentials = token

    # 3. 함수 실행 및 검증
    current_user = await get_current_user(auth_creds)
    assert current_user.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    auth_creds = MagicMock()
    auth_creds.credentials = "invalid-token"

    with pytest.raises(HTTPException) as exc:
        await get_current_user(auth_creds)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_not_found():
    # 존재하지 않는 유저 ID(9999)로 토큰 생성
    token = create_access_token(subject=9999)
    auth_creds = MagicMock()
    auth_creds.credentials = token

    with pytest.raises(HTTPException) as exc:
        await get_current_user(auth_creds)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_current_user_no_sub_in_token():
    """
    'sub' 필드가 없는 토큰을 전달하여
    deps.py의 'if user_id is None:' 로직을 실행시키고 커버리지를 올립니다.
    """
    # sub가 없는 페이로드로 직접 토큰 생성
    payload = {"exp": 9999999999}  # 만료 시간만 포함하고 sub는 누락
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    auth_creds = MagicMock()
    auth_creds.credentials = token

    with pytest.raises(HTTPException) as exc:
        await get_current_user(auth_creds)

    # deps.py에 정의된 에러 메시지와 일치하는지 확인
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.value.detail == "토큰에 유저 정보가 없습니다."


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_success(initialize_tests):
    # 1. 테스트 유저 및 리프레시 토큰 생성
    user = await User.create(
        provider_id="67890", provider=ProviderChoice.KAKAO, nickname="refresh_user"
    )
    token = create_refresh_token(subject=user.id)

    # 2. 쿠키로부터 유저 정보 추출 검증
    current_user = await get_current_user_from_refresh_cookie(refresh_token=token)
    assert current_user.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_no_token():
    # 토큰이 없을 때 401 에러 검증
    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_refresh_cookie(refresh_token=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Refresh token 존재하지 않음" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_invalid_type():
    # 리프레시 토큰이 아닌 액세스 토큰을 넣었을 때 에러 검증
    token = create_access_token(subject=1)
    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_refresh_cookie(refresh_token=token)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_wrong_payload():
    # payload에 sub는 있지만 type이 'refresh'가 아닌 경우 (라인 74 커버)
    payload = {"sub": "1", "type": "access"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_refresh_cookie(refresh_token=token)
    assert exc.value.detail == "Invalid refresh token"


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_decode_error():
    # 조작된 토큰으로 decode 에러 유도 (라인 82 커버)
    with pytest.raises(HTTPException) as exc:
        await get_current_user_from_refresh_cookie(refresh_token="totally.invalid.token")
    assert exc.value.detail == "Could not validate refresh token"


@pytest.mark.asyncio
async def test_get_current_user_by_cognito_success(mocker):
    from app.domains.users.models import User

    # 1. Cognito 검증 모킹
    mocker.patch("app.api.deps.verify_cognito_token", return_value={"sub": "cognito_sub_123"})
    # 2. DB 유저 조회 모킹
    mock_user = mocker.Mock(spec=User)
    mocker.patch(
        "app.domains.users.models.User.get_or_none", new_callable=AsyncMock, return_value=mock_user
    )

    auth_creds = mocker.Mock()
    auth_creds.credentials = "valid_cognito_token"

    user = await get_current_user_by_cognito(auth_creds)
    assert user == mock_user


@pytest.mark.asyncio
async def test_get_current_user_from_refresh_cookie_ws_fail(mocker):
    from fastapi.exceptions import WebSocketException

    from app.api.deps import get_current_user_from_refresh_cookie_ws

    # 쿠키가 없는 WebSocket 객체 모킹
    mock_ws = mocker.Mock()
    mock_ws.cookies = {}

    with pytest.raises(WebSocketException) as exc:
        await get_current_user_from_refresh_cookie_ws(mock_ws)
    assert exc.value.code == 1008


@pytest.mark.asyncio
async def test_deps_websocket_auth(mocker):
    mock_ws = mocker.Mock()
    # 쿠키 없음 (Line 146)
    mock_ws.cookies = {}
    with pytest.raises(WebSocketException):
        await get_current_user_from_refresh_cookie_ws(mock_ws)

    # 정상 흐름 (Line 143-153)
    mock_ws.cookies = {"refresh_token": "valid"}
    mocker.patch("app.api.deps.get_user_from_refresh_token", return_value=mocker.Mock())
    user = await get_current_user_from_refresh_cookie_ws(mock_ws)
    assert user is not None
