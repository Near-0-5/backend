from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import settings
from app.domains.streams.admin.schemas import StreamWebhookPayload
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.deps import get_stream_admin_service

router = APIRouter(prefix="/streams/webhook", tags=["스트리밍 웹훅"])


@router.post(
    "", status_code=status.HTTP_200_OK, summary="IVS 상태 변경 웹훅", include_in_schema=False
)
async def ivs_webhook_handler(
    payload: StreamWebhookPayload,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    service: StreamAdminService = Depends(get_stream_admin_service),
) -> None:
    """
    AWS EventBridge IVS 상태 변경 수신
    """
    # 보안 키 확인
    if not x_api_key or x_api_key != settings.IVS_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    await service.handle_ivs_webhook(payload)
