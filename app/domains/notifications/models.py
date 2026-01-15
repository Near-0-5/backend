from tortoise import fields, models

from app.domains.streams.models import Concert
from app.domains.users.models import User


class UserNoti(models.Model):
    # User와 1:1 관계
    user: fields.OneToOneRelation["User"] = fields.OneToOneField(
        "models.User", related_name="noti_setting", pk=True
    )
    artist_noti = fields.BooleanField(default=True)
    live_noti = fields.BooleanField(default=True)
    marketing_noti = fields.BooleanField(default=False)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_notis"


class ConcertNoti(models.Model):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="concert_notis"
    )
    concert: fields.ForeignKeyRelation["Concert"] = fields.ForeignKeyField(
        "models.Concert", related_name="scheduled_notis"
    )
    title = fields.CharField(max_length=100)
    message = fields.TextField()
    send_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "concert_notis"
