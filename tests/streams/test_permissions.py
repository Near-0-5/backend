from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.domains.streams.models import AccessLevel, Concert
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_verify_playback_access_public_allows():
    """PUBLIC 모든 유저"""
    user = MagicMock(spec=User)
    user.is_superuser = False

    concert = MagicMock(spec=Concert)
    concert.access_level = AccessLevel.PUBLIC

    await StreamPermission.verify_playback_access(user, concert)


@pytest.mark.asyncio
async def test_verify_playback_access_admin_only_denied():
    """ADMIN_ONLY 관리자만 접근 가능"""
    user = MagicMock(spec=User)
    user.is_superuser = False

    concert = MagicMock(spec=Concert)
    concert.access_level = AccessLevel.ADMIN_ONLY

    with pytest.raises(HTTPException) as exc:
        await StreamPermission.verify_playback_access(user, concert)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_playback_access_specific_requires_ticket():
    """SPECIFIC 티켓(권한) 있어야 접근 가능"""
    user = MagicMock(spec=User)
    user.is_superuser = False

    concert = MagicMock(spec=Concert)
    concert.access_level = AccessLevel.SPECIFIC

    with pytest.raises(HTTPException) as exc:
        await StreamPermission.verify_playback_access(user, concert)

    assert exc.value.status_code == 402
