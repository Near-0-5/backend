from fastapi import APIRouter, Query, WebSocket

from app.domains.chat.manager import ConnectionManager
from app.domains.chat.service import ChatService

router = APIRouter(prefix="", tags=["chat"])

manager = ConnectionManager()
service = ChatService(manager)


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, room_id: str = Query(...), user_id: str = Query(...)) -> None:
    """
    WebSocket 채팅 엔드포인트(임시 구현).

    Note(추후 개선):
        - 현재는 room_id / user_id를 쿼리 파라미터로 받아서 연결한다.
        - 운영 단계에서는 user_id를 쿼리로 받지 않고, WebSocket 핸드셰이크 시점의
        Authorization 헤더(JWT 등)에서 user_id를 추출하도록 변경한다.
        - room_id는 concert_id와 매핑하여 공연 존재 여부 및 참여 권한을
        서비스 레이어에서 인가(authorization)로 검증한 뒤 접속을 허용한다.
    """
    await service.handle_connection(ws=ws, room_id=room_id, user_id=user_id)
