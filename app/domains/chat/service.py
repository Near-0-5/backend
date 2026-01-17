import uuid
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

from app.domains.chat.manager import ConnectionManager
from app.domains.chat.schemas import ClientMessage, ServerEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatService:
    """
    개선사항:
        1) room_id == concert_id로 연결하여 공연 존재 여부를 확인 가능하도록 수정.
        2) user_id를 JWT에서 추출하도록 수정.
        3) user_id당 room 참여 제한.
        4) 메시지 전송 제한.
    """
    def __init__(self, manager: ConnectionManager) -> None:
        """
        ChatService 생성자.

        Args:
            manager (ConnectionManager): room_id별 WebSocket 연결 목록 관리 및 브로드캐스트를 담당하는 매니저
        """
        self.manager = manager

    async def handle_connectioin(self, ws: WebSocket, room_id: str, user_id: str) -> None:
        """
        특정 room_id 채팅방에 대해 WebSocket 연결을 처리하고,
        클라이언트 메시지를 수신하여 같은 방의 모든 접속자에게 브로드캐스트하는 메인 루프를 수행한다.

        Args:
            ws (WebSocket): 유저 1명과 서버 사이의 WebSocket 연결 객체(통로)
            room_id (str): 채팅방 식별자 (현재는 쿼리로 입력받는 값)
            user_id (str): 유저 식별자 (현재는 쿼리로 입력받는 값)

        Flow:
            1) room_id/user_id 문자열을 정리(strip)한다.
            2) _authorize_room_access로 해당 유저가 room에 참여 가능한지(인가) 확인한다.
            3) manager.connect로 연결을 등록하고, 입장(system) 이벤트를 브로드캐스트한다.
            4) 무한 루프에서 클라이언트 메시지를 수신(receive_json)한다.
            5) ClientMessage 스키마로 입력을 검증한 뒤,
            ServerEvent로 서버 이벤트를 구성하여 manager.broadcast_json으로 방 전체에 전송한다.
            6) WebSocketDisconnect 발생 시 연결을 해제하고 퇴장(system) 이벤트를 브로드캐스트한다.
            7) 기타 예외 발생 시 연결을 정리하고 가능하면 소켓을 close한다.

        Note:
            - 현재 구현은 user_id/room_id를 클라이언트 입력에 의존함.
            운영 단계에서는 인증(JWT)으로 user_id를 확정하고, 인가로 room 접근을 제한하는 방식으로 확장해아함.
        """
        room_id = room_id.strip()
        user_id = user_id.strip()

        await self._authorize_room_access(user_id=user_id, room_id=room_id)

        await self.manager.connect(room_id, ws)
        await self._broadcast_system(room_id, user_id, f"{user_id} joined")

        try:
            while True:
                data = await ws.receive_json()
                msg = ClientMessage.model_validate(data)

                evt = ServerEvent(
                    type="message",
                    room_id=room_id,
                    user_id=user_id,
                    text=msg.text,
                    ts=now_iso(),
                    message_id=str(uuid.uuid4()),
                    ).model_dump(),
                await self.manager.broadcast_json(room_id, evt)

        except WebSocketDisconnect:
            await self.manager.disconnect(room_id, ws)
            await self._broadcast_system(room_id, user_id, f"{user_id} left")

        except Exception:
            await self.manager.disconnect(room_id, ws)
            try:
                await ws.close()
            except Exception:
                pass

    async def _broadcast_system(self, room_id: str, user_id: str, text: str) -> None:
        """
        개선사항: 시스템 알람같은 경우 어떤식으로 채팅방에서 구현할지 논의 필요

        시스템(system) 이벤트(예: 입장/퇴장/공연 시작 알림)를 구성하여,
        해당 room_id의 모든 접속자에게 브로드캐스트한다.(유지할지 논의 필요)

        Args:
            room_id (str): 채팅방 식별자
            user_id (str): 이벤트 주체 유저 식별자
            text (str): 시스템 메시지 본문 (예: "{user_id} joined")

        Flow:
            1) ServerEvent(type="system") 형태의 이벤트 payload를 구성한다.
            2) manager.broadcast_json으로 room_id 전체에 전송한다.
        """
        evt = ServerEvent(
            type="system",
            room_id=room_id,
            user_id=user_id,
            text=text,
            ts=now_iso(),
            message_id=None,
        ).model_dump()
        await self.manager.broadcast_json(room_id, evt)


    async def _authorize_room_access(self, user_id: str, room_id: str) -> None:
        ...