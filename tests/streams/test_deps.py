from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.domains.streams import deps


def test_get_ivs_client():
    """IVS Client 생성 테스트"""
    client = deps.get_ivs_client()
    assert client is not None
    assert hasattr(client, "create_channel")


def test_get_playback_provider():
    """Playback Provider 생성 테스트"""
    provider = deps.get_playback_provider()
    assert provider is not None
    assert hasattr(provider, "sign_playback_token")


def test_get_stream_admin_service():
    """Admin Service DI 테스트"""
    service = deps.get_stream_admin_service()
    assert service is not None
    assert service.ivs_client is not None


def test_get_stream_user_service():
    """User Service DI 테스트"""
    service = deps.get_stream_user_service()
    assert service is not None
    assert service.ivs_client is not None
    assert service.playback_provider is not None


@pytest.mark.asyncio
async def test_get_admin_user_success():
    """어드민 유저 검증 성공 테스트"""
    # Mock 유저 생성 (슈퍼유저 권한 부여)
    mock_user = MagicMock()
    mock_user.is_superuser = True

    result = await deps.get_admin_user(current_user=mock_user)

    assert result == mock_user
    assert result.is_superuser is True


@pytest.mark.asyncio
async def test_get_admin_user_forbidden():
    """일반 유저가 어드민 권한 요청 시 403 에러 테스트"""
    # 일반 유저 Mock 생성
    mock_user = MagicMock()
    mock_user.is_superuser = False

    # 실행 시 HTTPException(403)이 발생하는지 검증
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_admin_user(current_user=mock_user)

    assert exc_info.value.status_code == 403
    assert "관리자만 접근이 가능합니다" in exc_info.value.detail
