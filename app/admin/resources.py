from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

import bcrypt
from fastadmin import TortoiseModelAdmin as _RuntimeTortoiseModelAdmin
from fastadmin import display, register
from fastapi import HTTPException

from app.admin.models import AdminUser
from app.domains.artists.models import Artist, Follow
from app.domains.concerts.models import Concert
from app.domains.notifications.models import ConcertNoti
from app.domains.streams.admin.schemas import ChannelConfig, SessionCreateRequest
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.models import (
    ConcertArtist,
    ConcertSession,
    StreamChannel,
    StreamSession,
    StreamVod,
)
from app.domains.users.models import User, UserCatFav, UserDeleteLog
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider

if TYPE_CHECKING:

    class TortoiseModelAdmin:  # pragma: no cover
        async def save_model(
            self, id: int | None, payload: dict[str, Any]
        ) -> dict[str, Any] | None: ...

        async def delete_model(self, id: int) -> None: ...

        def get_model_fields_with_widget_types(
            self, with_m2m: bool | None = None, with_upload: bool | None = None
        ) -> list[Any]: ...

        def deserialize_value(self, field: Any, value: Any) -> Any: ...

        async def orm_get_obj(self, id: int) -> Any | None: ...

        async def serialize_obj(self, obj: Any, list_view: bool = False) -> dict[str, Any]: ...
else:
    TortoiseModelAdmin = _RuntimeTortoiseModelAdmin

F = TypeVar("F", bound=Callable[..., Any])


def typed_display(func: F) -> F:
    return cast(F, display(func))


def _ko_plural(name: str) -> str:
    return f"{name} 목록"


@register(AdminUser)
class AdminUserAdmin(TortoiseModelAdmin):
    verbose_name = "관리자 계정"
    verbose_name_plural = _ko_plural(verbose_name)
    exclude = ("hash_password",)
    list_display = ("id", "username", "is_superuser", "is_active", "created_at")
    list_display_links = ("id", "username")
    list_filter = ("is_superuser", "is_active")
    search_fields = ("username",)
    search_help_text = "아이디 검색"
    ordering = ("-created_at",)

    @staticmethod
    def _hash_to_bytes(stored_hash: str | bytes | None) -> bytes | None:
        if not stored_hash:
            return None
        if isinstance(stored_hash, bytes):
            return stored_hash
        return stored_hash.encode("utf-8")

    async def authenticate(self, username: str, password: str) -> int | None:
        obj = await AdminUser.get_or_none(
            username=username,
            is_superuser=True,
            is_active=True,
        )
        if not obj:
            return None
        stored_hash = self._hash_to_bytes(obj.hash_password)
        if not stored_hash:
            return None
        try:
            if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                return None
        except (ValueError, TypeError):
            return None
        return obj.id

    async def change_password(self, id: int, password: str) -> None:
        obj = await AdminUser.get_or_none(id=id)
        if not obj:
            return
        obj.hash_password = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode()
        await obj.save(update_fields=["hash_password"])


@register(User)
class UserAdmin(TortoiseModelAdmin):
    verbose_name = "회원"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = (
        "id",
        "nickname",
        "email",
        "provider",
        "provider_id",
        "is_superuser",
        "created_at",
    )
    list_display_links = ("id", "nickname")
    list_filter = ("provider", "is_superuser")
    search_fields = ("nickname", "email", "provider_id")
    search_help_text = "닉네임/이메일/소셜 ID 검색"
    ordering = ("-created_at",)


@register(UserCatFav)
class UserCatFavAdmin(TortoiseModelAdmin):
    verbose_name = "회원 관심 카테고리"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "user", "category", "created_at")
    list_display_links = ("id", "user")
    list_filter = ("category",)
    search_fields = ("user__nickname", "user__email")
    search_help_text = "닉네임/이메일 검색"
    ordering = ("-created_at",)


@register(UserDeleteLog)
class UserDeleteLogAdmin(TortoiseModelAdmin):
    verbose_name = "회원 탈퇴 로그"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "user", "email", "deleted_at", "deleted_by", "created_at")
    list_display_links = ("id", "email")
    search_fields = ("email", "deleted_by")
    search_help_text = "이메일/삭제자 검색"
    ordering = ("-created_at",)


@register(Artist)
class ArtistAdmin(TortoiseModelAdmin):
    verbose_name = "아티스트"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = (
        "id",
        "stage_name",
        "category_type",
        "group_type",
        "debut_date",
        "created_at",
    )
    list_display_links = ("id", "stage_name")
    list_filter = ("category_type", "group_type")
    search_fields = ("stage_name", "agency")
    search_help_text = "활동명/소속사 검색"
    ordering = ("-created_at",)


@register(Follow)
class FollowAdmin(TortoiseModelAdmin):
    verbose_name = "팔로우"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "user", "artist", "created_at")
    list_display_links = ("id", "user")
    ordering = ("-created_at",)


@register(Concert)
class ConcertAdmin(TortoiseModelAdmin):
    verbose_name = "공연"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "title", "category", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("category",)
    search_fields = ("title",)
    search_help_text = "공연 제목 검색"
    ordering = ("-created_at",)


@register(ConcertSession)
class ConcertSessionAdmin(TortoiseModelAdmin):
    verbose_name = "공연 회차"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = (
        "id",
        "concert",
        "session_name",
        "status",
        "monitor_link",
        "access_level",
        "start_at",
        "end_at",
    )
    list_display_links = ("id", "session_name")
    list_filter = ("status", "access_level", "is_test")
    search_fields = ("session_name",)
    search_help_text = "회차명 검색"

    async def delete_model(self, id: int) -> None:
        service = StreamAdminService(
            ivs_client=IVSClient(), playback_provider=IVSPlaybackProvider()
        )
        await service.delete_session_with_infrastructure(id, user=cast("User", None))

    async def save_model(self, id: int | None, payload: dict[str, Any]) -> dict[str, Any] | None:
        if id is not None:
            return await super().save_model(id, payload)

        fields = self.get_model_fields_with_widget_types(with_m2m=False, with_upload=False)
        parsed_payload = {
            field.name: self.deserialize_value(field, payload[field.name])
            for field in fields
            if field.name in payload
        }

        concert_id = parsed_payload.pop("concert", None)
        if concert_id is None:
            raise HTTPException(status_code=422, detail="concert is required")
        if isinstance(concert_id, str):
            concert_id = int(concert_id)

        parsed_payload.pop("status", None)
        parsed_payload.pop("id", None)

        artist_ids = payload.get("lineup") or []
        artist_ids = [int(artist_id) for artist_id in artist_ids]

        data = SessionCreateRequest(
            **parsed_payload,
            artist_ids=artist_ids,
            channel_config=ChannelConfig(),
        )

        service = StreamAdminService(
            ivs_client=IVSClient(), playback_provider=IVSPlaybackProvider()
        )
        session_res = await service.create_session_with_infrastructure(
            concert_id, data, user=cast("User", None)
        )

        obj = await self.orm_get_obj(session_res.id)
        if not obj:
            return None
        return await self.serialize_obj(obj)

    @typed_display
    def monitor_link(self, obj: ConcertSession) -> str:
        from fastadmin.settings import settings as admin_settings

        url = f"/{admin_settings.ADMIN_PREFIX}/sessions/{obj.id}/monitor"
        return url

    monitor_link.short_description = "모니터링"  # type: ignore[attr-defined]


@register(ConcertArtist)
class ConcertArtistAdmin(TortoiseModelAdmin):
    verbose_name = "공연 출연진"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "session", "artist", "is_main", "created_at")
    list_display_links = ("id", "session")
    list_filter = ("is_main",)
    ordering = ("-created_at",)


@register(StreamChannel)
class StreamChannelAdmin(TortoiseModelAdmin):
    verbose_name = "스트리밍 채널"
    verbose_name_plural = _ko_plural(verbose_name)
    exclude = ("stream_key_encrypted",)
    list_display = (
        "id",
        "session",
        "type",
        "latency_mode",
        "is_private",
        "is_record",
        "created_at",
    )
    list_display_links = ("id", "session")
    list_filter = ("type", "latency_mode", "is_private", "is_record")
    ordering = ("-created_at",)

    async def delete_model(self, id: int) -> None:
        channel = await StreamChannel.get_or_none(id=id)
        if not channel:
            return
        session_id = getattr(channel, "session_id", None)
        if session_id is None:
            return
        service = StreamAdminService(
            ivs_client=IVSClient(), playback_provider=IVSPlaybackProvider()
        )
        await service.delete_session_with_infrastructure(int(session_id), user=cast("User", None))


@register(StreamSession)
class StreamSessionAdmin(TortoiseModelAdmin):
    verbose_name = "스트리밍 세션"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = ("id", "session", "stream_id", "started_at", "ended_at", "peak_viewers")
    list_display_links = ("id", "stream_id")
    search_fields = ("stream_id",)
    search_help_text = "스트림 ID 검색"


@register(StreamVod)
class StreamVodAdmin(TortoiseModelAdmin):
    verbose_name = "VOD"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = (
        "id",
        "session",
        "s3_bucket",
        "s3_key_prefix",
        "processing_status",
        "created_at",
    )
    list_display_links = ("id", "session")
    list_filter = ("processing_status",)
    search_fields = ("s3_bucket", "s3_key_prefix")
    search_help_text = "S3 버킷/경로 검색"
    ordering = ("-created_at",)


# @register(UserNoti)
# class UserNotiAdmin(TortoiseModelAdmin):
#     verbose_name = "회원 알림 설정"
#     verbose_name_plural = _ko_plural(verbose_name)
#     list_display = ("user", "artist_noti", "live_noti", "marketing_noti", "updated_at")
#     list_display_links = ("user",)
#     list_filter = ("artist_noti", "live_noti", "marketing_noti")


@register(ConcertNoti)
class ConcertNotiAdmin(TortoiseModelAdmin):
    verbose_name = "공연 알림"
    verbose_name_plural = _ko_plural(verbose_name)
    list_display = (
        "id",
        "user",
        "session",
        "kind",
        "status",
        "send_at",
        "sent_at",
        "created_at",
    )
    list_display_links = ("id", "user")
    list_filter = ("kind", "status")
    ordering = ("-created_at",)
