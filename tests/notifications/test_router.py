import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.config import now_kst
from app.domains.notifications.models import ConcertNoti, NotiKind, NotiStatus, UserNoti
from app.domains.streams.models import CategoryType, Concert, ConcertSession
from app.domains.users.models import ProviderChoice, User
from app.main import app


@pytest.mark.asyncio
async def test_get_notification_settings_creates_default() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_notice_settings",
        nickname="notice_settings",
    )

    async def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/notifications/settings")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["artist_noti"] is True
        assert data["live_noti"] is True
        assert data["marketing_noti"] is False
        assert "updated_at" in data

        assert await UserNoti.filter(user_id=user.id).count() == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_notification_settings_updates_fields() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_notice_settings_patch",
        nickname="notice_settings_patch",
    )

    async def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"artist_noti": False, "marketing_noti": True}
            response = await ac.patch("/api/v1/notifications/settings", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["artist_noti"] is False
        assert data["marketing_noti"] is True
        assert data["live_noti"] is True
        assert "updated_at" in data

        saved = await UserNoti.get(user_id=user.id)
        assert saved.artist_noti is False
        assert saved.marketing_noti is True
        assert saved.live_noti is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_notification_removes_only_user_record() -> None:
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_notice_delete",
        nickname="notice_delete",
    )
    concert = await Concert.create(title="Notice Delete", category=CategoryType.KPOP)
    session = await ConcertSession.create(
        concert=concert, session_name="Delete", start_at=now_kst()
    )
    noti = await ConcertNoti.create(
        user=user,
        session=session,
        kind=NotiKind.START,
        title="delete",
        message="msg",
        send_at=now_kst(),
        status=NotiStatus.PENDING,
    )

    async def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete(f"/api/v1/notifications/{noti.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert await ConcertNoti.filter(id=noti.id).count() == 0
    finally:
        app.dependency_overrides.clear()
