from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.domains.streams.models import AccessLevel
from app.domains.streams.permissions import StreamPermission


@pytest.mark.asyncio
class TestStreamPermission:
    def test_must_be_admin(self):
        # 관리자 통과
        admin = MagicMock(is_superuser=True)
        StreamPermission.must_be_admin(admin)

        # 일반인 거부
        user = MagicMock(is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            StreamPermission.must_be_admin(user)
        assert exc.value.status_code == 403

    async def test_verify_playback_access_logic(self):
        # 슈퍼유저 프리패스
        admin = MagicMock(is_superuser=True)
        await StreamPermission.verify_playback_access(admin, MagicMock())

        user = MagicMock(is_superuser=False)

        # PUBLIC 허용
        pub_session = MagicMock(access_level=AccessLevel.PUBLIC)
        await StreamPermission.verify_playback_access(user, pub_session)

        # ADMIN_ONLY 거부
        adm_session = MagicMock(access_level=AccessLevel.ADMIN_ONLY)
        with pytest.raises(HTTPException) as exc:
            await StreamPermission.verify_playback_access(user, adm_session)
        assert exc.value.status_code == 403

        # SPECIFIC 티켓 없음 거부
        spec_session = MagicMock(access_level=AccessLevel.SPECIFIC)
        with pytest.raises(HTTPException) as exc:
            await StreamPermission.verify_playback_access(user, spec_session)
        assert exc.value.status_code == 402
