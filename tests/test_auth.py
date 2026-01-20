from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.integrations.kakao import kakao_client


@pytest.mark.anyio
async def test_kakao_integration_coverage_boost(client, mocker):
    """라이브러리 설치 없이 kakao.py의 커버리지를 100% 가깝게 올리는 테스트"""

    # 1. httpx.AsyncClient의 post와 get 메서드를 모킹
    # kakao.py 내부의 'async with httpx.AsyncClient() as client:' 부분을 공략합니다.
    mock_response_token = MagicMock()
    mock_response_token.status_code = 200
    mock_response_token.json.return_value = {"access_token": "mock_access_token"}
    mock_response_token.raise_for_status = MagicMock()

    mock_response_user = MagicMock()
    mock_response_user.status_code = 200
    mock_response_user.json.return_value = {
        "id": 12345,
        "kakao_account": {"email": "test@kakao.com", "profile": {"nickname": "테스트"}},
    }
    mock_response_user.raise_for_status = MagicMock()

    # httpx.AsyncClient 내의 메서드들을 비동기로 모킹
    mock_client_instance = AsyncMock(spec=httpx.AsyncClient)
    mock_client_instance.post.return_value = mock_response_token
    mock_client_instance.get.return_value = mock_response_user
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # httpx.AsyncClient 생성자 자체를 가로챕니다.
    mocker.patch("httpx.AsyncClient", return_value=mock_client_instance)

    # 2. 실제 메서드 호출 (이때 kakao.py 내부의 모든 코드가 실행됩니다)
    token = await kakao_client.get_access_token("test_code")
    user_info = await kakao_client.get_user_info(token)

    # 3. 검증
    assert token == "mock_access_token"
    assert user_info["id"] == 12345
    assert user_info["kakao_account"]["email"] == "test@kakao.com"


@pytest.mark.anyio
async def test_kakao_callback_endpoint(client, mocker, initialize_tests):
    """엔드포인트 호출 시에도 커버리지가 유지되도록 처리"""
    # 위와 동일한 모킹 전략을 사용하여 실제 엔드포인트 호출
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
    mock_client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"id": 1, "kakao_account": {"email": "e", "profile": {"nickname": "n"}}},
    )

    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    response = await client.get("/api/v1/auth/kakao/callback?code=test_code")
    assert response.status_code == 200
