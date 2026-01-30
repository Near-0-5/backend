import bcrypt

from fastadmin import TortoiseModelAdmin, register

from app.admin.models import AdminUser
from app.domains.artists.models import Artist, Follow
from app.domains.notifications.models import ConcertNoti, UserNoti
from app.domains.streams.models import (
    Concert,
    ConcertArtist,
    ConcertSession,
    StreamChannel,
    StreamSession,
    StreamVod,
)
from app.domains.users.models import User, UserCatFav, UserDeleteLog


@register(AdminUser)
class AdminUserAdmin(TortoiseModelAdmin):
    exclude = ("hash_password",)
    list_display = ("id", "username", "is_superuser", "is_active", "created_at")
    list_display_links = ("id", "username")
    list_filter = ("is_superuser", "is_active")
    search_fields = ("username",)

    async def authenticate(self, username: str, password: str) -> int | None:
        obj = await AdminUser.get_or_none(
            username=username,
            is_superuser=True,
            is_active=True,
        )
        if not obj:
            return None
        stored_hash = obj.hash_password
        if not stored_hash:
            return None
        try:
            if not bcrypt.checkpw(password.encode("utf8"), stored_hash.encode("utf8")):
                return None
        except ValueError:
            return None
        return obj.id

    async def change_password(self, id: int, password: str) -> None:
        obj = await AdminUser.get(id=id)
        obj.hash_password = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode()
        await obj.save(update_fields=["hash_password"])


@register(User)
class UserAdmin(TortoiseModelAdmin):
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


@register(UserCatFav)
class UserCatFavAdmin(TortoiseModelAdmin):
    list_display = ("id", "user_id", "category", "created_at")
    list_display_links = ("id", "user_id")
    list_filter = ("category",)
    search_fields = ("user_id",)


@register(UserDeleteLog)
class UserDeleteLogAdmin(TortoiseModelAdmin):
    list_display = ("id", "user_id", "email", "deleted_at", "deleted_by")
    list_display_links = ("id", "email")
    search_fields = ("email", "deleted_by")


@register(Artist)
class ArtistAdmin(TortoiseModelAdmin):
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


@register(Follow)
class FollowAdmin(TortoiseModelAdmin):
    list_display = ("id", "user_id", "artist_id", "created_at")
    list_display_links = ("id", "user_id")


@register(Concert)
class ConcertAdmin(TortoiseModelAdmin):
    list_display = ("id", "title", "category", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("category",)
    search_fields = ("title",)


@register(ConcertSession)
class ConcertSessionAdmin(TortoiseModelAdmin):
    list_display = (
        "id",
        "concert_id",
        "session_name",
        "status",
        "access_level",
        "start_at",
        "end_at",
    )
    list_display_links = ("id", "session_name")
    list_filter = ("status", "access_level", "is_test")
    search_fields = ("session_name",)


@register(ConcertArtist)
class ConcertArtistAdmin(TortoiseModelAdmin):
    list_display = ("id", "session_id", "artist_id", "is_main", "created_at")
    list_display_links = ("id", "session_id")
    list_filter = ("is_main",)


@register(StreamChannel)
class StreamChannelAdmin(TortoiseModelAdmin):
    exclude = ("stream_key_encrypted",)
    list_display = (
        "id",
        "session_id",
        "type",
        "latency_mode",
        "is_private",
        "is_record",
        "created_at",
    )
    list_display_links = ("id", "session_id")
    list_filter = ("type", "latency_mode", "is_private", "is_record")


@register(StreamSession)
class StreamSessionAdmin(TortoiseModelAdmin):
    list_display = ("id", "session_id", "stream_id", "started_at", "ended_at", "peak_viewers")
    list_display_links = ("id", "stream_id")
    search_fields = ("stream_id",)


@register(StreamVod)
class StreamVodAdmin(TortoiseModelAdmin):
    list_display = (
        "id",
        "session_id",
        "s3_bucket",
        "s3_key_prefix",
        "processing_status",
        "created_at",
    )
    list_display_links = ("id", "session_id")
    list_filter = ("processing_status",)
    search_fields = ("s3_bucket", "s3_key_prefix")


@register(UserNoti)
class UserNotiAdmin(TortoiseModelAdmin):
    list_display = ("user_id", "artist_noti", "live_noti", "marketing_noti", "updated_at")
    list_display_links = ("user_id",)
    list_filter = ("artist_noti", "live_noti", "marketing_noti")


@register(ConcertNoti)
class ConcertNotiAdmin(TortoiseModelAdmin):
    list_display = (
        "id",
        "user_id",
        "session_id",
        "kind",
        "status",
        "send_at",
        "sent_at",
    )
    list_display_links = ("id", "user_id")
    list_filter = ("kind", "status")
