from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.users.models import User

# --- 기초 서비스 주입 테스트 ---


def test_get_ivs_client():
    client = streams_deps.get_ivs_client()
    assert client is not None
    assert hasattr(client, "create_channel")


def test_get_playback_provider():
    provider = streams_deps.get_playback_provider()
    assert provider is not None
    assert hasattr(provider, "sign_playback_token")


def test_get_stream_admin_service():
    service = streams_deps.get_stream_admin_service()
    assert service is not None
    assert service.ivs_client is not None


def test_get_stream_user_service():
    service = streams_deps.get_stream_user_service()
    assert service is not None
    assert service.ivs_client is not None
    assert service.playback_provider is not None


# --- get_admin_user 인증 흐름 테스트 ---


@pytest.mark.asyncio
async def test_get_admin_user_success():
    """인증 성공"""
    mock_user = MagicMock(spec=User)
    mock_user.is_superuser = True

    with patch(
        "app.api.deps.get_current_user",
        new_callable=AsyncMock,
    ) as mock_get_current:
        mock_get_current.return_value = mock_user

        result = await deps.get_admin_user(current_user=mock_user)

        assert result == mock_user
        mock_get_current.assert_not_called()


@pytest.mark.asyncio
async def test_get_admin_user_forbidden():
    """인증은 성공했으나 관리자 권한(is_superuser)이 없는 경우 (403 에러)"""
    mock_user = MagicMock(spec=User)
    mock_user.is_superuser = False  # 관리자 아님

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_admin_user(current_user=mock_user)

    # StreamPermission.must_be_admin()에서 발생시키는 403 체크
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
