import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from app.domains.chat.schemas import ServerEvent


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ConnectionLimits:
    """연결 제한 정책.
    - max_total: 서버 전체 동시 연결 상한
    - max_per_room: 방(=room_id)당 동시 연결 상한
    """

    max_total: int = 10_000
    max_per_room: int = 1_000


class ConnectionLimitError(RuntimeError):
    pass


class ConnectionManager:
    def __init__(self, *, limits: ConnectionLimits | None = None) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._limits = limits or ConnectionLimits()

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        """방 검증하고 소켓 연결 후 소켓(클라) 룸에 넣어버려"""
        await self._ensure_capacity(room_id)

        await ws.accept()

        try:
            await self.register(room_id, ws)
        except ConnectionLimitError:
            await self.close_safe(ws, code=1008)
            raise

    async def register(self, room_id: str, ws: WebSocket) -> None:
        """방에 소켓을 등록"""
        async with self._lock:
            # 서버 전체
            total = sum(len(v) for v in self._rooms.values())
            if total >= self._limits.max_total:
                raise ConnectionLimitError("server is busy")

            # 방 단위
            room_set = self._rooms.get(room_id)
            room_size = len(room_set) if room_set else 0
            if room_size >= self._limits.max_per_room:
                raise ConnectionLimitError("room is full")

            if room_set is None:
                room_set = set()
                self._rooms[room_id] = room_set

            room_set.add(ws)

    async def disconnect(self, room_id: str, ws: WebSocket) -> None:
        """방에서 소켓(클라) 제거해버려"""
        async with self._lock:
            room_set = self._rooms.get(room_id)
            if not room_set:
                return

            room_set.discard(ws)
            if not room_set:
                self._rooms.pop(room_id, None)

    async def broadcast_json(self, room_id: str, payload: dict[str, Any]) -> None:
        """방에있는 소켓(클라) 전체에 모두 뿌려버려."""
        async with self._lock:
            targets = list(self._rooms.get(room_id, set()))

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                room_set = self._rooms.get(room_id)
                if room_set:
                    for ws in dead:
                        room_set.discard(ws)
                    if not room_set:
                        self._rooms.pop(room_id, None)

    async def send_system_to_self(self, ws: WebSocket, *, room_id: str, user_id: str, text: str) -> None:
        """소켓(클라)마다 고유한 서버 알림 줘버려"""
        payload = ServerEvent(
            type="system",
            room_id=room_id,
            user_id=user_id,
            text=text,
            ts=now_iso(),
            message_id=None,
        ).model_dump()
        await ws.send_json(payload)

    async def close_safe(self, ws: WebSocket, *, code: int) -> None:
        """close는 실패해도 상관없는 경우가 많아서 safe helper로 둠."""
        try:
            await ws.close(code=code)
        except Exception:
            return

    async def _ensure_capacity(self, room_id: str) -> None:
        """방에 소켓 등록 전 확인하기
        accept 하고 1008로 끊는 비용 줄이기 위한 검증"""
        async with self._lock:
            # 서버 자체에 트레픽 많아지면 예외처리 줘버려
            total = sum(len(v) for v in self._rooms.values())
            if total >= self._limits.max_total:
                raise ConnectionLimitError("server is busy")

            # 방에 사람 많으면 예외처리 줘버려
            room_set = self._rooms.get(room_id)
            room_size = len(room_set) if room_set else 0
            if room_size >= self._limits.max_per_room:
                raise ConnectionLimitError("room is full")