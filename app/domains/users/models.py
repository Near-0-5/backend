from enum import Enum

from tortoise import fields, models

from app.domains.streams.models import CategoryType


# 소셜 제공자
class ProviderChoice(str, Enum):
    KAKAO = "KAKAO"
    GOOGLE = "GOOGLE"


# 성별
class GenderChoices(str, Enum):
    M = "M"  # MALE
    F = "F"  # FEMALE


class User(models.Model):
    id = fields.IntField(pk=True)
    provider = fields.CharEnumField(ProviderChoice, max_length=20)
    provider_id = fields.CharField(max_length=255, unique=True)
    email = fields.CharField(max_length=100, null=True)
    nickname = fields.CharField(max_length=30, unique=True)
    profile_img_url = fields.CharField(max_length=255, null=True)
    bio = fields.TextField(null=True, description="자기소개")
    gender = fields.CharEnumField(GenderChoices, max_length=1, null=True)
    birth_date = fields.DateField(null=True)
    is_superuser = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class UserCatFav(models.Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="cat_favs"
    )
    category = fields.CharEnumField(CategoryType)  # Enum 사용
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_cat_favs"


class UserDeleteLog(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.IntField()
    email = fields.CharField(max_length=100, null=True)
    reason = fields.CharField(max_length=200, null=True)
    deleted_at = fields.DatetimeField()
    deleted_by = fields.CharField(max_length=50)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users_delete_logs"
