import uuid
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

from app.domains.chat.manager import ConnectionManager
from app.domains.chat.schemas import ClientMessage, ServerEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatService:
    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager

    async def handle_connectioin(self, ws: WebSocket, room_id: str, user_id: str) -> None:
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