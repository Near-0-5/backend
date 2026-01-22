import threading
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient, WebSocketTestSession

from app.main import app


def find_chat_ws_route(app: FastAPI) -> WebSocketRoute:
    ws_routes = [r for r in app.router.routes if isinstance(r, WebSocketRoute)]
    for r in ws_routes:
        if "/streaming/" in r.path and r.path.endswith("/chat"):
            return r
    for r in ws_routes:
        if "chat" in r.path:
            return r
    raise AssertionError(
        f"채팅 WebSocketRoute를 못 찾았음. ws_routes={[r.path for r in ws_routes]}"
    )


def build_ws_url(route: WebSocketRoute, *, room_id: str, user_id: str) -> str:
    path = route.path

    if "{stream_id}" in path:
        return path.replace("{stream_id}", room_id) + f"?user_id={user_id}"

    if "chat" in path:
        sep = "&" if "?" in path else "?"
        return f"{path}{sep}room_id={room_id}&user_id={user_id}"

    raise AssertionError(f"지원하지 않는 WS path 템플릿: {path}")


def recv_until(
    ws_sess: WebSocketTestSession,
    want_type: str,
    *,
    timeout: float = 2.0,
    max_reads: int = 50,
) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    err: BaseException | None = None

    def _run() -> None:
        nonlocal result, err
        last: Any = None
        try:
            for _ in range(max_reads):
                evt = ws_sess.receive_json()
                last = evt
                if isinstance(evt, dict) and evt.get("type") == want_type:
                    result = evt
                    return
            err = AssertionError(f"'{want_type}' 이벤트 못 찾았음. last={last}")
        except BaseException as e:
            err = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        raise AssertionError(f"'{want_type}' 이벤트를 {timeout}s 내에 못 받았음(대기 상태).")

    if err:
        raise err

    assert result is not None
    return result


@pytest.fixture()
def client() -> TestClient:
    c = TestClient(app)
    yield c
    c.close()


@pytest.fixture()
def patch_stream_exists_true():
    with patch("app.domains.chat.service.StreamChannel.exists", new=AsyncMock(return_value=True)):
        yield


class TestChatWebSocket:
    def test_ws_connect_recent_ok(self, client: TestClient, patch_stream_exists_true) -> None:
        route = find_chat_ws_route(app)
        room_id = "12345"
        user_id = "1"
        url = build_ws_url(route, room_id=room_id, user_id=user_id)

        with client.websocket_connect(url) as w:
            recent = recv_until(w, "recent")
            assert recent["type"] == "recent"
            assert str(recent.get("room_id")) == room_id
            assert isinstance(recent.get("items"), list)

            sys_evt = recv_until(w, "system")
            assert sys_evt["type"] == "system"
            assert sys_evt["room_id"] == room_id
            assert sys_evt["user_id"] == user_id

    def test_ws_send_message_echo_ok(self, client: TestClient, patch_stream_exists_true) -> None:
        route = find_chat_ws_route(app)
        room_id = "23456"
        user_id = "1"
        url = build_ws_url(route, room_id=room_id, user_id=user_id)

        with client.websocket_connect(url) as w:
            _ = recv_until(w, "recent")
            _ = recv_until(w, "system")

            w.send_json({"type": "message", "text": "안녕"})
            evt = recv_until(w, "message")

            assert evt["type"] == "message"
            assert evt["room_id"] == room_id
            assert evt["user_id"] == user_id
            assert evt["text"] == "안녕"
            assert "ts" in evt
            assert evt.get("message_id")

    def test_ws_rate_limit_returns_system(
        self, client: TestClient, patch_stream_exists_true
    ) -> None:
        route = find_chat_ws_route(app)
        room_id = "34567"
        user_id = "1"
        url = build_ws_url(route, room_id=room_id, user_id=user_id)

        with client.websocket_connect(url) as w:
            _ = recv_until(w, "recent")
            _ = recv_until(w, "system")

            w.send_json({"type": "message", "text": "첫번째"})
            _ = recv_until(w, "message")

            w.send_json({"type": "message", "text": "두번째"})
            sys_evt = recv_until(w, "system")
            assert sys_evt["type"] == "system"
            assert "2초" in sys_evt.get("text", "")
