import asyncio
import contextlib
import json
from typing import Any

from fastapi import WebSocket

from app.core.redis import redis_client

NOTIFICATION_CHANNEL = "notifications"


class NotificationConnectionManager:
    def __init__(self, *, max_total: int = 10_000, max_per_user: int = 5) -> None:
        self._users: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._max_total = max_total
        self._max_per_user = max_per_user
        self._subscriber_task: asyncio.Task[None] | None = None


    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._ensure_capacity_locked(user_id)
            self._add_ws_locked(user_id, ws)

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._remove_ws_locked(user_id, ws)

    async def send_json(self, user_id: str, payload: dict[str, Any]) -> int:
        async with self._lock:
            targets = list(self._users.get(user_id, set()))

        delivered, dead = await self._send_to_targets(targets, payload)

        if dead:
            async with self._lock:
                self._prune_dead_locked(user_id, dead)

        return delivered

    async def publish(self, user_id: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"user_id": user_id, "payload": payload})
        await redis_client.publish(NOTIFICATION_CHANNEL, message)

    async def ensure_subscriber(self) -> None:
        if self._subscriber_task and not self._subscriber_task.done():
            return
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())


    def _total_connections_locked(self) -> int:
        return sum(len(conns) for conns in self._users.values())

    def _ensure_capacity_locked(self, user_id: str) -> None:
        if self._total_connections_locked() >= self._max_total:
            raise RuntimeError("server is busy")

        room = self._users.get(user_id)
        if room and len(room) >= self._max_per_user:
            raise RuntimeError("too many connections")

    def _add_ws_locked(self, user_id: str, ws: WebSocket) -> None:
        room = self._users.setdefault(user_id, set())
        room.add(ws)

    def _remove_ws_locked(self, user_id: str, ws: WebSocket) -> None:
        room = self._users.get(user_id)
        if not room:
            return
        room.discard(ws)
        if not room:
            self._users.pop(user_id, None)

    def _prune_dead_locked(self, user_id: str, dead: list[WebSocket]) -> None:
        room = self._users.get(user_id)
        if not room:
            return
        for ws in dead:
            room.discard(ws)
        if not room:
            self._users.pop(user_id, None)


    async def _send_to_targets(
        self, targets: list[WebSocket], payload: dict[str, Any]
    ) -> tuple[int, list[WebSocket]]:
        delivered = 0
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
                delivered += 1
            except Exception:
                dead.append(ws)
        return delivered, dead

    def _decode_pubsub_data(self, data: Any) -> str | None:
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except Exception:
                return None
        if isinstance(data, str):
            return data
        return None

    def _parse_pubsub_message(self, raw: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        if raw.get("type") != "message":
            return None

        data_str = self._decode_pubsub_data(raw.get("data"))
        if not data_str:
            return None

        try:
            msg = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        user_id = msg.get("user_id")
        payload = msg.get("payload")

        if not user_id or not isinstance(payload, dict):
            return None

        return str(user_id), payload

    async def _subscriber_loop(self) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(NOTIFICATION_CHANNEL)

        try:
            async for raw in pubsub.listen():
                parsed = self._parse_pubsub_message(raw)
                if not parsed:
                    continue
                user_id, payload = parsed
                await self.send_json(user_id, payload)
        except asyncio.CancelledError:
            pass
        finally:
            with contextlib.suppress(Exception):
                await pubsub.close()


notification_manager = NotificationConnectionManager()