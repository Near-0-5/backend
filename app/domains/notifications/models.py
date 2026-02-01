from enum import Enum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.domains.streams.models import ConcertSession
    from app.domains.users.models import User


class NotiKind(str, Enum):
    DAY_BEFORE = "DAY_BEFORE"
    HOUR_1 = "HOUR_1"
    MIN_30 = "MIN_30"
    START = "START"


class NotiStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class UserNoti(models.Model):
    user: fields.OneToOneRelation["User"] = fields.OneToOneField(
        "models.User",
        related_name="noti_setting",
        on_delete=fields.CASCADE,
        primary_key=True,
    )
    artist_noti = fields.BooleanField(default=True)
    live_noti = fields.BooleanField(default=True)
    marketing_noti = fields.BooleanField(default=False)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_notis"

    def __str__(self) -> str:
        user_id = getattr(self, "user_id", None)
        return f"user_id={user_id}"


class ConcertNoti(models.Model):
    id = fields.BigIntField(primary_key=True)

    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="concert_notis"
    )
    session: fields.ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="scheduled_notis"
    )

    if TYPE_CHECKING:
        user_id: int
        session_id: int

    kind = fields.CharEnumField(NotiKind, db_index=True)

    title = fields.CharField(max_length=100)
    message = fields.TextField()

    send_at = fields.DatetimeField(db_index=True)

    status = fields.CharEnumField(NotiStatus, default=NotiStatus.PENDING, db_index=True)
    sent_at = fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "concert_notis"
        unique_together = (("user", "session", "kind"),)
        indexes = (("status", "send_at"),)

    def __str__(self) -> str:
        user_id = getattr(self, "user_id", None)
        session_id = getattr(self, "session_id", None)
        return f"user_id={user_id} session_id={session_id} kind={self.kind}"
