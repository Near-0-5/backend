from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


def ws(room_id: int | str, user_id: int | str) -> str:
    return f"/api/v1/ws/chat?room_id={room_id}&user_id={user_id}"


def recv_until(ws_sess, want_type: str, max_reads: int = 30) -> dict:
    last = None
    for _ in range(max_reads):
        try:
            evt = ws_sess.receive_json()
        except WebSocketDisconnect as e:
            raise AssertionError(
                f"WebSocket이 먼저 끊김(code={getattr(e, 'code', None)}). "
                f"원하던 type='{want_type}' 못 받았음. 마지막 이벤트={last}"
            ) from e

        last = evt
        if isinstance(evt, dict) and evt.get("type") == want_type:
            return evt

    raise AssertionError(f"'{want_type}' 이벤트를 못 찾았음. 마지막 이벤트={last}")


def assert_message(evt: dict, *, room_id, user_id, text: str) -> None:
    assert evt["type"] == "message"
    assert str(evt.get("room_id")) == str(room_id)
    assert str(evt.get("user_id")) == str(user_id)
    assert evt.get("text") == text
    assert "ts" in evt


class TestChatWebSocket:
    def setup_method(self) -> None:
        self.client = TestClient(app)

    def teardown_method(self) -> None:
        self.client.close()

    def test_ws_connect_ok(self) -> None:
        with self.client.websocket_connect(ws(1, 1)):
            pass

    def test_ws_send_message_receive_broadcast(self) -> None:
        with self.client.websocket_connect(ws(1, 1)) as w:
            w.send_json({"type": "message", "text": "안녕"})
            evt = recv_until(w, "message")
            assert_message(evt, room_id=1, user_id=1, text="안녕")

    def test_ws_broadcast_to_other_client(self) -> None:
        c1 = TestClient(app)
        c2 = TestClient(app)
        try:
            with c1.websocket_connect(ws(1, 1)) as w1, c2.websocket_connect(ws(1, 2)) as w2:
                w1.send_json({"type": "message", "text": "hello"})

                _ = recv_until(w1, "message")
                evt2 = recv_until(w2, "message")
                assert_message(evt2, room_id=1, user_id=1, text="hello")
        finally:
            c1.close()
            c2.close()

    def test_import_thin_modules(self) -> None:
        import app.main