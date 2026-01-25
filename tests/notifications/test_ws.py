from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient

from app.api.deps import get_current_user_from_refresh_cookie_ws
from app.main import app


def find_notifications_ws_route(app_: FastAPI) -> WebSocketRoute:
    ws_routes = [r for r in app_.router.routes if isinstance(r, WebSocketRoute)]
    for route in ws_routes:
        if route.path.endswith("/notifications/ws"):
            return route
    raise AssertionError(
        f"notifications WebSocketRoute를 못 찾았음. ws_routes={[r.path for r in ws_routes]}"
    )


@pytest.fixture()
def ws_client() -> TestClient:
    client = TestClient(app)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def override_ws_user():
    async def _override(ws: WebSocket) -> SimpleNamespace:
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_current_user_from_refresh_cookie_ws] = _override
    yield
    app.dependency_overrides.clear()


def test_notifications_ws_connects(ws_client: TestClient) -> None:
    route = find_notifications_ws_route(app)
    with (
        patch(
            "app.domains.notifications.service.notification_manager.ensure_subscriber",
            new=AsyncMock(),
        ),
        ws_client.websocket_connect(route.path) as ws,
    ):
        ws.send_text("ping")
