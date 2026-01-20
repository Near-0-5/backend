from typing import Any

from fastapi import APIRouter, Depends

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.service import StreamService
from app.domains.users.models import User

router = APIRouter(prefix="/streams", tags=["Streaming"])


@router.get("/{concert_id}/credentials", summary="스트림 시청 권한 확인 - 토큰 발급")
async def get_stream_access(
    concert_id: int,
    current_user: User = Depends(deps.get_current_user),
    service: StreamService = Depends(streams_deps.get_streams_service),
) -> dict[str, Any]:
    """
    해당 콘서트의 시청 자격 검증 -> IVS 재생 토큰 + 채팅용 세션 토큰 반환
    """
    return await service.get_viewing_credentials(concert_id, current_user)
