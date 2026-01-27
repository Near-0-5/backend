from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domains.notifications.models import NotiKind, NotiStatus


class NotificationSettingsUpdate(BaseModel):
    artist_noti: bool | None = None
    live_noti: bool | None = None
    marketing_noti: bool | None = None


class NotificationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artist_noti: bool
    live_noti: bool
    marketing_noti: bool
    updated_at: datetime


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    kind: NotiKind
    title: str
    message: str
    send_at: datetime
    status: NotiStatus
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    items: list[NotificationItem]


class NotificationEvent(BaseModel):
    type: Literal["notification"] = "notification"
    notification: NotificationItem
