import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.domains.notifications.manager import (
    NOTIFICATION_CHANNEL,
    NotificationConnectionManager,
)


class DummyWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []
        self._fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, object]) -> None:
        if self._fail_send:
            raise RuntimeError("send failed")
        self.sent.append(payload)


class FakePubSub:
    def __init__(self, messages: list[dict[str, object]], *, raise_cancel: bool = False) -> None:
        self._messages = messages
        self._raise_cancel = raise_cancel
        self.subscribed: str | None = None
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self.subscribed = channel

    async def close(self) -> None:
        self.closed = True

    async def listen(self):
        if self._raise_cancel:
            raise asyncio.CancelledError()
        for message in self._messages:
            yield message


class FakeRedis:
    def __init__(self, pubsub: FakePubSub) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> FakePubSub:
        return self._pubsub


@pytest.mark.asyncio
async def test_manager_connect_disconnect_and_capacity() -> None:
    manager = NotificationConnectionManager(max_total=1, max_per_user=1)
    ws1 = DummyWebSocket()
    await manager.connect("u1", ws1)
    assert ws1.accepted is True
    assert manager._users["u1"] == {ws1}

    ws2 = DummyWebSocket()
    with pytest.raises(RuntimeError, match="server is busy"):
        await manager.connect("u2", ws2)

    manager = NotificationConnectionManager(max_total=10, max_per_user=1)
    ws3 = DummyWebSocket()
    ws4 = DummyWebSocket()
    await manager.connect("u1", ws3)
    with pytest.raises(RuntimeError, match="too many connections"):
        await manager.connect("u1", ws4)

    await manager.disconnect("u1", ws3)
    assert "u1" not in manager._users

    await manager.disconnect("missing", ws3)


@pytest.mark.asyncio
async def test_manager_send_json_prunes_dead_and_removes_empty() -> None:
    manager = NotificationConnectionManager()
    good = DummyWebSocket()
    bad = DummyWebSocket(fail_send=True)
    await manager.connect("u1", good)
    await manager.connect("u1", bad)

    delivered = await manager.send_json("u1", {"ok": True})
    assert delivered == 1
    assert manager._users["u1"] == {good}

    manager._prune_dead_locked("missing", [bad])

    manager2 = NotificationConnectionManager()
    only_bad = DummyWebSocket(fail_send=True)
    await manager2.connect("u2", only_bad)
    delivered = await manager2.send_json("u2", {"ok": True})
    assert delivered == 0
    assert "u2" not in manager2._users


@pytest.mark.asyncio
async def test_manager_publish_calls_redis() -> None:
    manager = NotificationConnectionManager()
    mock_publish = AsyncMock()
    fake_redis = SimpleNamespace(publish=mock_publish)

    with patch("app.domains.notifications.manager.redis_client", new=fake_redis):
        await manager.publish("u1", {"ok": True})

    mock_publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_ensure_subscriber_creates_task() -> None:
    manager = NotificationConnectionManager()
    dummy_task = SimpleNamespace(done=lambda: False)

    with (
        patch(
            "app.domains.notifications.manager.asyncio.create_task", return_value=dummy_task
        ) as create_task,
        patch.object(manager, "_subscriber_loop", new=AsyncMock()),
    ):
        await manager.ensure_subscriber()

    assert manager._subscriber_task is dummy_task
    create_task.assert_called_once()

    manager._subscriber_task = SimpleNamespace(done=lambda: False)
    with patch("app.domains.notifications.manager.asyncio.create_task") as create_task:
        await manager.ensure_subscriber()
    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_manager_decode_and_parse_pubsub() -> None:
    manager = NotificationConnectionManager()

    assert manager._decode_pubsub_data(b"ok") == "ok"
    assert manager._decode_pubsub_data("text") == "text"
    assert manager._decode_pubsub_data(123) is None
    assert manager._decode_pubsub_data(b"\xff") is None

    assert manager._parse_pubsub_message({"type": "subscribe"}) is None
    assert manager._parse_pubsub_message({"type": "message", "data": None}) is None
    assert manager._parse_pubsub_message({"type": "message", "data": "{"}) is None
    assert (
        manager._parse_pubsub_message({"type": "message", "data": '{"user_id": "", "payload": {}}'})
        is None
    )
    assert (
        manager._parse_pubsub_message(
            {"type": "message", "data": '{"user_id": "1", "payload": "no"}'}
        )
        is None
    )
    assert manager._parse_pubsub_message(
        {"type": "message", "data": '{"user_id": "1", "payload": {"a": 1}}'}
    ) == ("1", {"a": 1})


@pytest.mark.asyncio
async def test_manager_subscriber_loop_processes_messages() -> None:
    manager = NotificationConnectionManager()
    pubsub = FakePubSub(
        [
            {"type": "subscribe", "data": "ignored"},
            {"type": "message", "data": '{"user_id": "1", "payload": {"a": 1}}'},
        ]
    )
    fake_redis = FakeRedis(pubsub)

    with (
        patch("app.domains.notifications.manager.redis_client", new=fake_redis),
        patch.object(manager, "send_json", new=AsyncMock()) as mock_send,
    ):
        await manager._subscriber_loop()

    assert pubsub.subscribed == NOTIFICATION_CHANNEL
    assert pubsub.closed is True
    mock_send.assert_awaited_once_with("1", {"a": 1})


@pytest.mark.asyncio
async def test_manager_subscriber_loop_handles_cancel() -> None:
    manager = NotificationConnectionManager()
    pubsub = FakePubSub([], raise_cancel=True)
    fake_redis = FakeRedis(pubsub)

    with patch("app.domains.notifications.manager.redis_client", new=fake_redis):
        await manager._subscriber_loop()

    assert pubsub.subscribed == NOTIFICATION_CHANNEL
    assert pubsub.closed is True
