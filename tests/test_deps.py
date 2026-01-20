from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token
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
