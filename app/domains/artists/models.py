from tortoise import fields, models

from app.domains.users.models import User


class Artist(models.Model):
    id = fields.IntField(pk=True)
    stage_name = fields.CharField(max_length=100)
    profile_img_url = fields.CharField(max_length=255, null=True)
    agency = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    debut_date = fields.DateField(null=True)
    member_count = fields.IntField(null=True)
    group_type = fields.CharField(max_length=50, null=True)
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
