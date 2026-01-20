from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.models import AccessLevel, CategoryType, ChannelType, Concert, LatencyMode
from app.domains.streams.schemas import ChannelConfig, ConcertCreateRequest
from app.domains.streams.service import StreamService
from app.domains.users.models import User
from app.main import app


# Mock Objects 준비
@pytest.fixture
def mock_user() -> User:
    """테스트용 관리자 유저 객체"""
    user = MagicMock(spec=User)
    user.id = 1
    user.is_superuser = True
    user.is_active = True
    return user


@pytest.fixture
def mock_service() -> MagicMock:
    """비즈니스 로직을 담당하는 StreamsService 모킹"""
    service = MagicMock(spec=StreamService)

    # 관리자용 방송 생성 리턴값 설정
    mock_concert = MagicMock(spec=Concert)
    mock_concert.id = 999
    mock_concert.title = "테스트 콘서트"
    mock_concert.access_level = AccessLevel.PUBLIC
    mock_concert.created_at = "2026-01-20T22:00:00"

    service.create_concert_and_channel = AsyncMock(return_value=mock_concert)

    # 유저용 자격 증명 리턴값 설정
    service.get_viewing_credentials = AsyncMock(
        return_value={
            "playback_url": "https://test.m3u8",
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
        }
    )
    return service


@pytest.fixture
def client(mock_user, mock_service) -> TestClient:
    """FastAPI 의존성을 교체(Override)한 테스트 클라이언트"""
    # 실제 인증 및 서비스 생성을 Mock으로 교체
    app.dependency_overrides[deps.get_current_user] = lambda: mock_user
    app.dependency_overrides[streams_deps.get_streams_service] = lambda: mock_service

    with TestClient(app) as c:
        yield c

    # 테스트 종료 후 복구
    app.dependency_overrides.clear()


def test_admin_setup_endpoint(client: TestClient) -> None:
    """관리자 방송 생성 API 테스트"""
    from datetime import datetime

    request_obj = ConcertCreateRequest(
        category=CategoryType.KPOP,
        title="테스트 콘서트",
        start_at=datetime(2026, 1, 20, 22, 0, 0, tzinfo=UTC),
        access_level=AccessLevel.PUBLIC,
        channel_config=ChannelConfig(
            latency_mode=LatencyMode.LOW, channel_type=ChannelType.STANDARD
        ),
    )

    payload = request_obj.model_dump(mode="json")
    response = client.post("/api/v1/admin/streams/setup", json=payload)

    # 에러 발생 시 상세 내용을 확인하기 위해 로깅 추가
    if response.status_code != 201:
        print(f"Validation Error Detail: {response.json()}")

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 999
    assert data["title"] == "테스트 콘서트"


def test_user_credentials_endpoint(client: TestClient) -> None:
    """유저 시청 권한 발급 API 테스트"""
    concert_id = 999
    response = client.get(f"/api/v1/streams/{concert_id}/credentials")

    assert response.status_code == 200
    data = response.json()
    assert "playback_url" in data
    assert data["access_token"] == "mock_access"


@pytest.mark.asyncio
async def test_permission_denied_for_normal_user(mock_service):
    """일반 유저가 관리자 기능을 호출할 때의 권한 체크(Service Level)"""
    from fastapi import HTTPException

    # Given: 일반 유저 준비
    normal_user = MagicMock(spec=User)
    normal_user.is_superuser = False

    # 실제 서비스 인스턴스 (Mock 아님) 사용하여 로직 검증
    # StreamPermission.must_be_admin(user) 가 내부에서 작동하는지 확인
    from app.domains.streams.service import StreamService

    service = StreamService(MagicMock(), MagicMock())

    # When & Then
    with pytest.raises(HTTPException) as exc:
        await service.create_concert_and_channel(MagicMock(), normal_user)

    assert exc.value.status_code == 403
