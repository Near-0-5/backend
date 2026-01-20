from fastapi import APIRouter, HTTPException, status

from app.domains.streams.models import StreamChannel

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/streaming/{stream_id}/validate")
async def validate_chat_room(stream_id: str) -> dict[str, bool]:
    """
    프런트용 사전 검증 API.
    - stream_id가 잘못되면 400
    - 스트림이 없으면 404
    - (추후) 권한 없으면 403
    """

    try:
        sid = int(stream_id.strip())
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid stream_id"
        ) from err

    exists = await StreamChannel.exists(id=sid)
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stream not found")

    return {"ok": True}
