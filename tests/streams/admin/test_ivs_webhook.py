from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestIVSWebhookRouter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.webhook_url = "/api/v1/streams/webhook"
        self.valid_payload = {
            "version": "0",
            "id": "test-id",
            "detail-type": "IVS Stream State Change",
            "source": "aws.ivs",
            "time": "2024-01-01T00:00:00Z",
            "region": "ap-northeast-2",
            "resources": ["arn:aws:ivs:ap-northeast-2:123456789012:channel/abc"],
            "detail": {
                "channel_arn": "arn:aws:ivs:ap-northeast-2:123456789012:channel/abc",
                "event_name": "Stream End",
                "stream_id": "st-123",
                "channel_name": "test-channel",
            },
        }

    # API KEY가 없거나 틀렸을 때
    async def test_ivs_webhook_invalid_key(self, client: AsyncClient):
        # 헤더 없이 요청
        response = await client.post(self.webhook_url, json=self.valid_payload)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid API Key"

        # 틀린 헤더로 요청
        headers = {"X-API-Key": "wrong-secret-key"}
        response = await client.post(self.webhook_url, json=self.valid_payload, headers=headers)
        assert response.status_code == 403

    # 정상 요청 시
    async def test_ivs_webhook_success(self, client: AsyncClient):
        from app.core.config import settings

        headers = {"X-API-Key": settings.IVS_WEBHOOK_SECRET}

        with patch(
            "app.domains.streams.admin.service.StreamAdminService.handle_ivs_webhook",
            new_callable=AsyncMock,
        ) as mock_handle:
            response = await client.post(self.webhook_url, json=self.valid_payload, headers=headers)

            assert response.status_code == 200
            mock_handle.assert_called_once()
