from fastapi import APIRouter, Body, Depends, Path, status

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.admin.schemas import (
    ConcertCreateRequest,
    ConcertResponse,
    SessionCreateRequest,
    SessionResponse,
)
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.models import Concert
from app.domains.users.models import User

router = APIRouter(prefix="/admin/streams", tags=["[Admin] Streaming"])


@router.post(
    "/concerts",
    status_code=status.HTTP_201_CREATED,
    response_model=ConcertResponse,
    summary="콘서트 메타정보 생성",
    description="신규 콘서트의 기본 메타데이터(제목, 카테고리 등)를 생성합니다. \
    인프라 리소스는 생성되지 않습니다.",
)
async def create_concert(
    data: ConcertCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> Concert:
    return await service.create_concert(data, current_user)


@router.post(
    "/concerts/{concert_id}/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="콘서트 세션 생성 - IVS 채널 자동 설정",
    response_model=SessionResponse,
    description="특정 콘서트의 회차를 생성하고, AWS IVS 채널 리소스를 자동으로 할당합니다.",
)
async def create_concert_stream(
    concert_id: int = Path(..., description="콘서트 ID"),
    data: SessionCreateRequest = Body(..., description="새로운 콘서트 세션과 IVS config 상세 정보"),
    current_user: User = Depends(deps.get_current_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    """
    1. 콘서트 회차(Session) 레코드를 생성합니다.
    2. AWS IVS `CreateChannel` API를 호출하여 송출/재생 엔드포인트를 확보합니다.
    3. 발급된 스트림 키는 내부 보안 정책에 따라 암호화하여 저장합니다.
    """
    return await service.create_session_with_infrastructure(concert_id, data, current_user)
