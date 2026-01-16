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

