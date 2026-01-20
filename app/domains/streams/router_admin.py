from fastapi import APIRouter, Depends
from starlette import status

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.models import Concert
from app.domains.streams.schemas import ConcertCreateRequest, ConcertResponse
from app.domains.streams.service import StreamService
from app.domains.users.models import User

router = APIRouter(prefix="/admin/streams", tags=["[Admin] Streaming"])


@router.post(
    "/setup",
    status_code=status.HTTP_201_CREATED,
    response_model=ConcertResponse,
    summary="콘서트 생성 - IVS 채널 자동 설정",
)
async def create_concert_stream(
    data: ConcertCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    service: StreamService = Depends(streams_deps.get_streams_service),
) -> Concert:
    """
    관리자 권한으로 신규 콘서트 생성 -> AWS IVS 인프라 할당
    """
    return await service.create_concert_and_channel(data, current_user)
