from fastapi import APIRouter, WebSocket, Path, Depends

from app.domains.chat.manager import ConnectionLimits, ConnectionManager
from app.domains.chat.service import ChatPrecheckError, ChatService
from app.domains.users.models import User
from app.api.deps import get_current_user_from_refresh_cookie_ws

router = APIRouter(prefix="", tags=["chat"])

manager = ConnectionManager(limits=ConnectionLimits(max_total=10_000, max_per_room=1_000))
service = ChatService(manager)


@router.websocket("/streaming/{stream_id}/chat")
async def chat_ws(ws: WebSocket, stream_id: str = Path(...), user: User = Depends(get_current_user_from_refresh_cookie_ws)) -> None:
    """검증 후 WS 연결해벌여"""
    try:
        room_id = await service.precheck_room(stream_id)
    except ChatPrecheckError as err:
        raise service.precheck_to_http_exc(err) from err

    await service.handle_connection(ws=ws, room_id=room_id, user_id=str(user.id))
