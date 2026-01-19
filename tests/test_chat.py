import threading
import uuid

from starlette.testclient import TestClient

from app.main import app


def ws(room_id: str, user_id: str) -> str:
    return f"/api/v1/ws/chat?room_id={room_id}&user_id={user_id}"


def recv_until(ws_sess, want_type: str, *, timeout: float = 2.0, max_reads: int = 50) -> dict:
    result: dict | None = None
    err: BaseException | None = None

    def _run():
        nonlocal result, err
        last = None
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


class TestChatWebSocket:
    def setup_method(self) -> None:
        self.client = TestClient(app)

    def teardown_method(self) -> None:
        self.client.close()

    def test_ws_connect_and_recent_ok(self) -> None:
        room_id = f"t-{uuid.uuid4().hex}"
        with self.client.websocket_connect(ws(room_id, "1")) as w:
            recent = recv_until(w, "recent")
            assert recent["type"] == "recent"
            assert str(recent.get("room_id")) == room_id
            assert isinstance(recent.get("items"), list)

    def test_ws_send_message_echo_ok(self) -> None:
        room_id = f"t-{uuid.uuid4().hex}"
        with self.client.websocket_connect(ws(room_id, "1")) as w:
            _ = recv_until(w, "recent")

            w.send_json({"type": "message", "text": "안녕"})
            evt = recv_until(w, "message")

            assert evt["type"] == "message"
            assert str(evt.get("room_id")) == room_id
            assert str(evt.get("user_id")) == "1"
            assert evt.get("text") == "안녕"
            assert "ts" in evt

    def test_import_thin_modules(self) -> None:
        pass
