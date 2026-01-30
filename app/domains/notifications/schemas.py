from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.notifications.models import NotiKind, NotiStatus


class NotificationSettingsUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "artist_noti": True,
                    "live_noti": True,
                    "marketing_noti": False,
                }
            ]
        }
    )

    artist_noti: bool | None = Field(
        default=None,
        description="아티스트 관련 알림 수신 여부",
        examples=[True],
    )
    live_noti: bool | None = Field(
        default=None,
        description="라이브/스트리밍 관련 알림 수신 여부",
        examples=[True],
    )
    marketing_noti: bool | None = Field(
        default=None,
        description="마케팅/프로모션 알림 수신 여부",
        examples=[False],
    )


class NotificationSettingsResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "artist_noti": True,
                    "live_noti": True,
                    "marketing_noti": False,
                    "updated_at": "2025-01-01T12:00:00+00:00",
                }
            ]
        },
    )

    artist_noti: bool = Field(description="아티스트 관련 알림 수신 여부")
    live_noti: bool = Field(description="라이브/스트리밍 관련 알림 수신 여부")
    marketing_noti: bool = Field(description="마케팅/프로모션 알림 수신 여부")
    updated_at: datetime = Field(description="설정 최종 변경 시각 (UTC, ISO-8601)")


class NotificationItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "session_id": 101,
                    "kind": "START",
                    "title": "라이브 시작 알림",
                    "message": "지금 바로 공연이 시작됩니다.",
                    "send_at": "2025-01-01T12:00:00+00:00",
                    "status": "SENT",
                    "sent_at": "2025-01-01T12:00:01+00:00",
                    "created_at": "2024-12-31T10:00:00+00:00",
                    "updated_at": "2025-01-01T12:00:01+00:00",
                }
            ]
        },
    )

    id: int = Field(description="알림 고유 ID")
    session_id: int = Field(description="연결된 스트리밍 세션 ID")
    kind: NotiKind = Field(description="알림 종류 (DAY_BEFORE/HOUR_1/MIN_30/START)")
    title: str = Field(description="알림 제목")
    message: str = Field(description="알림 본문")
    send_at: datetime = Field(description="발송 예정 시각 (UTC, ISO-8601)")
    status: NotiStatus = Field(description="발송 상태 (PENDING/PROCESSING/SENT/FAILED)")
    sent_at: datetime | None = Field(description="실제 발송 시각 (발송 전에는 null)")
    created_at: datetime = Field(description="생성 시각 (UTC, ISO-8601)")
    updated_at: datetime = Field(description="마지막 변경 시각 (UTC, ISO-8601)")


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total": 1,
                    "items": [
                        {
                            "id": 1,
                            "session_id": 101,
                            "kind": "START",
                            "title": "라이브 시작 알림",
                            "message": "지금 바로 공연이 시작됩니다.",
                            "send_at": "2025-01-01T12:00:00+00:00",
                            "status": "SENT",
                            "sent_at": "2025-01-01T12:00:01+00:00",
                            "created_at": "2024-12-31T10:00:00+00:00",
                            "updated_at": "2025-01-01T12:00:01+00:00",
                        }
                    ],
                }
            ]
        }
    )

    total: int = Field(description="전체 알림 개수")
    items: list[NotificationItem] = Field(description="알림 목록")


class NotificationEvent(BaseModel):
    type: Literal["notification"] = Field(
        "notification",
        description="서버 이벤트 타입 (고정값: notification)",
        examples=["notification"],
    )
    notification: NotificationItem = Field(description="단일 알림 데이터")
