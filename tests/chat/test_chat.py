import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient, WebSocketTestSession

from app.main import app


def find_chat_ws_route(app_: FastAPI) -> WebSocketRoute:
    ws_routes = [r for r in app_.router.routes if isinstance(r, WebSocketRoute)]
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
    """
    현재 서버는 WS에서 user_id를 쿼리로 안 쓰지만,
    기존 테스트 유틸과 호환을 위해 그대로 남겨둠땃.
    """
    path = route.path

    if "{stream_id}" in path:
        # /streaming/{stream_id}/chat
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


# ✅ WS 인증(depends)을 테스트용으로 무조건 통과시키기
@pytest.fixture(autouse=True)
def override_ws_user():
    from app.api.deps import get_current_user_from_refresh_cookie_ws

    async def _override(ws: WebSocket):  # ✅ 타입 힌트 필수!
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_current_user_from_refresh_cookie_ws] = _override
    yield
    app.dependency_overrides.clear()


# ✅ stream 존재 검증을 통과시키기 (ConcertSession.exists 패치)
@pytest.fixture()
def patch_stream_exists_true():
    with (
        patch(
            "app.domains.chat.service.ConcertSession.exists",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.domains.chat.service.StreamChannel.exists",
            new=AsyncMock(return_value=True),
        ),
    ):
        yield


# ✅ Redis/Repo 의존성 제거: recent/append 기본 패치
@pytest.fixture()
def patch_chat_repo_base():
    with (
        patch(
            "app.domains.chat.service.get_recent_messages",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.domains.chat.service.append_chat_message",
            new=AsyncMock(return_value=None),
        ),
    ):
        yield


class TestChatWebSocket:
    def test_ws_connect_recent_ok(
        self,
        client: TestClient,
        patch_stream_exists_true,
        patch_chat_repo_base,
    ) -> None:
        # rate_limit은 연결/최근메시지에는 필요 없지만, 안전하게 항상 True로
        with patch("app.domains.chat.service.rate_limit_ok", new=AsyncMock(return_value=True)):
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
                # 실제 user_id는 dependency override의 id를 string으로 넘긴 값
                assert sys_evt["user_id"] == "1"

    def test_ws_send_message_echo_ok(
        self,
        client: TestClient,
        patch_stream_exists_true,
        patch_chat_repo_base,
    ) -> None:
        with patch("app.domains.chat.service.rate_limit_ok", new=AsyncMock(return_value=True)):
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
                assert evt["user_id"] == "1"
                assert evt["text"] == "안녕"
                assert "ts" in evt
                assert evt.get("message_id")

    def test_ws_rate_limit_returns_system(
        self,
        client: TestClient,
        patch_stream_exists_true,
        patch_chat_repo_base,
    ) -> None:
        # 첫 메시지는 통과, 두 번째는 차단하도록 side_effect
        with patch(
            "app.domains.chat.service.rate_limit_ok",
            new=AsyncMock(side_effect=[True, False]),
        ):
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
