import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.main import app

# Tortoise-ORM 테스트 설정
_CONFIG = {
    "connections": {"default": "sqlite://:memory:"},
    "apps": {
        "models": {
            "models": [
                "app.domains.users.models",
                "app.domains.notifications.models",
                "app.domains.artists.models",
                "app.domains.streams.models",
                "aerich.models",
            ],
            "default_connection": "default",
        }
    },
}

@pytest.fixture(autouse=True)
async def initialize_tests():
    """
    테스트 시작 전 DB 초기화 및 종료 후 정리 (비동기 방식)
    KeyError: 'models' 에러를 방지하기 위해 app_label을 명시적으로 초기화합니다.
    """
    # 1. DB 초기화 (initializer 대신 Tortoise.init 사용으로 확실하게 연결)
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": _CONFIG["apps"]["models"]["models"]}
    )

    # 2. 스키마 생성
    await Tortoise.generate_schemas()

    yield

    # 3. 테스트 종료 후 연결 종료
    await Tortoise.close_connections()

@pytest.fixture
async def client():
    """httpx.AsyncClient 설정 (FastAPI app 연결)"""
    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            # 필요 시 팔로우 리다이렉트 기본값 설정 가능
            follow_redirects=False
    ) as ac:
        yield ac