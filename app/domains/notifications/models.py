from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.domains.streams.models import ConcertSession
    from app.domains.users.models import User


class UserNoti(models.Model):
    # User와 1:1 관계
    user: fields.OneToOneRelation["User"] = fields.OneToOneField(
        "models.User", related_name="noti_setting", on_delete=fields.CASCADE, primary_key=True
    )
    artist_noti = fields.BooleanField(default=True)
    live_noti = fields.BooleanField(default=True)
    marketing_noti = fields.BooleanField(default=False)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_notis"


class ConcertNoti(models.Model):
    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="concert_notis"
    )
    session: fields.ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="scheduled_notis"
    )
    title = fields.CharField(max_length=100)
    message = fields.TextField()
    send_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "concert_notis"
        unique_together = ("user", "session")
