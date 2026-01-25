from fastapi import APIRouter, Depends, WebSocket

from app.api.deps import get_current_user_from_refresh_cookie_ws
from app.domains.notifications.service import notification_service
from app.domains.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])



@router.websocket("/ws")
async def notifications_ws(
    ws: WebSocket,
    user: User = Depends(get_current_user_from_refresh_cookie_ws),
) -> None:
    await notification_service.handle_ws_connection(ws, user_id=user.id)
