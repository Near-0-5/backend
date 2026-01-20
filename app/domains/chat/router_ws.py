from fastapi import APIRouter, Query, WebSocket

from app.domains.chat.manager import ConnectionLimits, ConnectionManager
from app.domains.chat.service import ChatPrecheckError, ChatService

router = APIRouter(prefix="", tags=["chat"])

manager = ConnectionManager(limits=ConnectionLimits(max_total=10_000, max_per_room=1_000))
service = ChatService(manager)


@router.websocket("/streaming/{stream_id}/chat")
async def chat_ws(ws: WebSocket, stream_id: str, user_id: str = Query(...)) -> None:
    """검증 후 WS 연결해벌여"""
    try:
        room_id = await service.precheck_room(stream_id)
    except ChatPrecheckError as err:
        raise service.precheck_to_http_exc(err) from err

    await service.handle_connection(ws=ws, room_id=room_id, user_id=user_id)
