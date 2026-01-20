from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.kakao import kakao_client


@pytest.mark.asyncio
async def test_get_access_token_success(mocker):
    # httpx.AsyncClient.post 모킹
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"access_token": "mocked_kakao_token"}
    mock_response.raise_for_status = mocker.Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        token = await kakao_client.get_access_token("valid_code")

        assert token == "mocked_kakao_token"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_get_user_info_success(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"id": 12345, "kakao_account": {"email": "test@kakao.com"}}
    mock_response.raise_for_status = mocker.Mock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        user_info = await kakao_client.get_user_info("mocked_token")

        assert user_info["id"] == 12345
        assert user_info["kakao_account"]["email"] == "test@kakao.com"