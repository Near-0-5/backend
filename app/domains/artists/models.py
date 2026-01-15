from enum import Enum

from tortoise import fields, models

from app.domains.users.models import User


# 그룹 형태
class GroupType(str, Enum):
    SOLO = "SOLO"  # 솔로
    GIRL_GROUP = "GIRL_GROUP"  # 걸그룹
    BOY_BAND = "BOY_BAND"  # 보이그룹
    MIXED_GROUP = "MIXED_GROUP"  # 혼성그룹


class Artist(models.Model):
    id = fields.IntField(pk=True)
    stage_name = fields.CharField(max_length=100, description="활동명")
    profile_img_url = fields.CharField(max_length=255, null=True)
    agency = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    debut_date = fields.DateField(null=True)
    member_count = fields.IntField(null=True)
    group_type = fields.CharEnumField(GroupType, max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "artists"


class Follow(models.Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="follows"
    )
    artist: fields.ForeignKeyRelation["Artist"] = fields.ForeignKeyField(
        "models.Artist", related_name="followers"
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "follows"
        unique_together = (("user", "artist"),)
