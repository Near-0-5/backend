from fastapi.testclient import TestClient

from app.main import app


class TestChatWebSocket:
    def setup_method(self) -> None:
        self.client = TestClient(app)

    def test_ws_connect_ok(self) -> None:
        with self.client.websocket_connect("/api/v1/ws/chat?room_id=1&user_id=1") as ws:
            pass

    def test_ws_send_message_receive_broadcast(self) -> None:
        with self.client.websocket_connect("/api/v1/ws/chat?room_id=1&user_id=1") as ws:
            _ = ws.receive_json()

            ws.send_json({"type": "message", "text": "안녕"})
            evt = ws.receive_json()

            assert evt["type"] == "message"
            assert evt["room_id"] == "1"
            assert evt["user_id"] == "1"
            assert evt["text"] == "안녕"
            assert "ts" in evt

    def test_ws_broadcast_to_other_client(self) -> None:
        with self.client.websocket_connect("/api/v1/ws/chat?room_id=1&user_id=최건희") as ws1:
            _ = ws1.receive_json()

            with self.client.websocket_connect("/api/v1/ws/chat?room_id=1&user_id=최강록") as ws2:
                _ = ws2.receive_json()

                ws1.send_json({"type": "message", "text": "hello"})
                evt2 = ws2.receive_json()

                assert evt2["type"] == "message"
                assert evt2["room_id"] == "1"
                assert evt2["user_id"] == "최건희"
                assert evt2["text"] == "hello"
                assert "ts" in evt2

    def test_import_thin_modules(self) -> None:
        import app.api.deps
        import app.domains.chat.router