from fastapi import APIRouter, Depends, Path, Query, WebSocket, status

from app.api.deps import get_current_user, get_current_user_from_refresh_cookie_ws
from app.domains.notifications.models import NotiStatus
from app.domains.notifications.schemas import (
    NotificationListResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
)
from app.domains.notifications.service import notification_service
from app.domains.users.models import User

router = APIRouter(prefix="/notifications", tags=["알림"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="알림 목록 조회",
    description="현재 로그인한 사용자의 알림 목록을 조회합니다.",
)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    status_filter: NotiStatus | None = Query(
        default=None,
        alias="status",
        description="알림 상태 필터 (PENDING/PROCESSING/SENT/FAILED)",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="조회 개수 (기본 50, 최대 200)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="시작 위치 (0부터 시작)",
    ),
) -> NotificationListResponse:
    items, total = await notification_service.list_user_notifications(
        current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(total=total, items=items)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="알림 삭제",
    description="사용자 알림 1건을 삭제합니다.",
)
async def delete_notification(
    notification_id: int = Path(..., description="삭제할 알림 ID"),
    current_user: User = Depends(get_current_user),
) -> None:
    await notification_service.delete_user_notification(current_user.id, notification_id)
    return None


@router.get(
    "/settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="알림 설정 조회",
    description="현재 로그인한 사용자의 알림 설정을 조회합니다.",
)
async def get_settings(
    current_user: User = Depends(get_current_user),
) -> NotificationSettingsResponse:
    settings = await notification_service.get_user_settings(current_user.id)
    return NotificationSettingsResponse.model_validate(settings)


@router.patch(
    "/settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="알림 설정 변경",
    description="알림 수신 설정을 부분 변경합니다. 전달하지 않은 값은 유지됩니다.",
)
async def update_settings(
    data: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> NotificationSettingsResponse:
    settings = await notification_service.update_user_settings(current_user.id, data)
    return NotificationSettingsResponse.model_validate(settings)


@router.websocket("/ws", name="알림 WebSocket")
async def notifications_ws(
    ws: WebSocket,
    user: User = Depends(get_current_user_from_refresh_cookie_ws),
) -> None:
    await notification_service.handle_ws_connection(ws, user_id=user.id)
