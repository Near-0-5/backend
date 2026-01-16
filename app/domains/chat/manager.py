import asyncio
from collections import defaultdict
from typing import DefaultDict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[room_id].add(ws)

    async def disconnect(self, room_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[room_id].discard(ws)
            if not self._rooms[room_id]:
                self._rooms.pop(room_id, None)

    async def broadcast_json(self, room_id: str, payload: dict) -> None:
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
                for ws in dead:
                    self._rooms[room_id].discard(ws)
                if room_id in self._rooms and not self._rooms[room_id]:
                    self._rooms.pop(room_id, None)