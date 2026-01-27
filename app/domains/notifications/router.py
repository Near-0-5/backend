from fastapi import APIRouter, Depends, Query, WebSocket, status

from app.api.deps import get_current_user, get_current_user_from_refresh_cookie_ws
from app.domains.notifications.models import NotiStatus
from app.domains.notifications.schemas import NotificationListResponse
from app.domains.notifications.service import notification_service
from app.domains.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=NotificationListResponse, status_code=status.HTTP_200_OK)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    status_filter: NotiStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    items, total = await notification_service.list_user_notifications(
        current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(total=total, items=items)

@router.websocket("/ws")
async def notifications_ws(
    ws: WebSocket,
    user: User = Depends(get_current_user_from_refresh_cookie_ws),
) -> None:
    await notification_service.handle_ws_connection(ws, user_id=user.id)
