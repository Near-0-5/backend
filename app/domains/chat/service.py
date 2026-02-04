import asyncio
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic_core import ValidationError

from app.domains.chat.manager import ConnectionLimitError, ConnectionManager
from app.domains.chat.repository import append_chat_message, get_recent_messages, rate_limit_ok
from app.domains.chat.schemas import ClientMessage, ServerEvent
from app.domains.streams.models import ConcertSession


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


IDLE_TIMEOUT_SECONDS: int | None = 60 * 30


class ChatPrecheckError(Exception):
    """핸드셰이크 전에 검증할 때 쓰는 도메인 에러."""


class InvalidRoomId(ChatPrecheckError):
    pass


class StreamNotFound(ChatPrecheckError):
    pass


class ChatService:
    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager

    # 핸드셰이크 전에 호출 가능한 검증
    async def precheck_room(self, room_id: str) -> str:
        room_id = room_id.strip()

        try:
            stream_id = int(room_id)
        except ValueError as err:
            raise InvalidRoomId("Invalid stream_id") from err

        exists = await ConcertSession.exists(id=stream_id)
        if not exists:
            raise StreamNotFound("stream not found")

        return str(stream_id)

    # 검증 API에서 ws 접속 전 사전에 HTTP-Exception를 받을 수 있음.
    def precheck_to_http_exc(self, err: ChatPrecheckError) -> HTTPException:
        if isinstance(err, InvalidRoomId):
            return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
        if isinstance(err, StreamNotFound):
            return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad request")

    async def handle_connection(self, ws: WebSocket, room_id: str, user_id: str) -> None:
        room_id = room_id.strip()
        user_id = user_id.strip()
        if not await ConcertSession.exists(id=int(room_id)):
            return

        try:
            await self.manager.connect(room_id, ws)
        except ConnectionLimitError:
            # accept 전에 터질 수도 있고, accept 후 1008로 닫혔을 수도 있음.
            return

        # 코드 최적화를 위한 시스템 메시지 전송 함수임.
        async def sys(text: str) -> None:
            await self.manager.send_system_to_self(ws, room_id=room_id, user_id=user_id, text=text)

        try:
            # recent 알림 (본인에게만)
            items = await get_recent_messages(room_id, limit=50)
            await ws.send_json({"type": "recent", "room_id": room_id, "items": items})

            # 연결 성공 알림 (본인에게만)
            await sys("채팅방에 입장하였습니다.")

            # main loop
            while True:
                # 메시지 요청시간 초과하면 루프 끊어버림;
                try:
                    if IDLE_TIMEOUT_SECONDS is None:
                        data = await ws.receive_json()
                    else:
                        data = await asyncio.wait_for(
                            ws.receive_json(), timeout=IDLE_TIMEOUT_SECONDS
                        )
                except TimeoutError:
                    # timeout 상황에선 이미 연결이 맛갔을 수도 있으니 send 실패해도 조용히 무시
                    with suppress(Exception):
                        await sys("무응답 시간 초과")
                    break

                # 메시지 형식 검증 후 이상하면 예외처리 후 continue
                try:
                    msg = ClientMessage.model_validate(data)
                except ValidationError:
                    with suppress(Exception):
                        await sys("메시지 형식이 올바르지 않숩나다")
                    continue

                # rate limit 검증
                ok = await rate_limit_ok(room_id, user_id)
                if not ok:
                    with suppress(Exception):
                        await sys("메시지는 2초에 1개만 보낼 수 있습니다")
                    continue

                # event build
                evt = self._build_message_event(
                    room_id=room_id,
                    user_id=user_id,
                    text=msg.text,
                )

                # 저장 실패해도 broadcast는 진행시켜
                with suppress(Exception):
                    await append_chat_message(room_id, evt)

                await self.manager.broadcast_json(room_id, evt)

        except WebSocketDisconnect:
            pass

        except Exception:
            with suppress(Exception):
                await self.manager.close_safe(ws, code=1011)
            raise
        finally:
            await self.manager.disconnect(room_id, ws)

    def _build_message_event(self, room_id: str, user_id: str, text: str) -> dict[str, Any]:
        return ServerEvent(
            type="message",
            room_id=room_id,
            user_id=user_id,
            text=text,
            ts=now_iso(),
            message_id=str(uuid.uuid4()),
        ).model_dump()
