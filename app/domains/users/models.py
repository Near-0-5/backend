from enum import Enum
from typing import TYPE_CHECKING

from tortoise import fields, models

from app.domains.streams.models import CategoryType

if TYPE_CHECKING:
    from app.domains.artists.models import Artist
    from app.domains.notifications.models import UserNoti


# 소셜 제공자
class ProviderChoice(str, Enum):
    KAKAO = "KAKAO"
    GOOGLE = "GOOGLE"
    NAVER = "NAVER"


# 성별
class GenderChoices(str, Enum):
    M = "M"  # MALE
    F = "F"  # FEMALE


class User(models.Model):
    id = fields.IntField(primary_key=True)
    provider = fields.CharEnumField(ProviderChoice, max_length=20)  # kakao, google 등
    provider_id = fields.CharField(max_length=255, unique=True)
    email = fields.CharField(max_length=100, null=True)
    real_name = fields.CharField(max_length=50, null=True)
    nickname = fields.CharField(max_length=30, unique=True)
    profile_img_url = fields.CharField(max_length=255, null=True)
    bio = fields.TextField(null=True, description="자기소개")
    gender = fields.CharEnumField(GenderChoices, max_length=1, null=True)
    phone_number = fields.CharField(max_length=20, null=True)  # 국제형식 및 하이픈 고려
    birth_date = fields.DateField(null=True)  # (yyyy-mm-dd)

    is_superuser = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    noti_setting: 'fields.OneToOneRelation["UserNoti"]'

    # 아티스트 팔로우 (M2M)  수정예정
    followed_artists: fields.ManyToManyRelation["Artist"] = fields.ManyToManyField(
        "models.Artist",
        through="follows",
        related_name="follower_users",
        forward_key="artist_id",
        backward_key="user_id",
    )

    fav_categories = fields.ReverseRelation["UserCatFav"]

    class Meta:
        table = "users"


class UserCatFav(models.Model):
    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="fav_categories"
    )
    category = fields.CharEnumField(CategoryType)  # Enum 사용
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_cat_favs"
        unique_together = (("user", "category"),)  # 동일 유저 동일 카테고리 중복 추가 방지


class UserDeleteLog(models.Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()  # 로그가 남아야함에 FK 미사용
    email = fields.CharField(max_length=100, null=True)
    reason = fields.CharField(max_length=200, null=True)
    deleted_at = fields.DatetimeField()
    deleted_by = fields.CharField(max_length=50)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users_delete_logs"
