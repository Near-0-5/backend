from fastapi import (
    APIRouter,
    Body,
    Depends,
    Path,
    Query,
    status,
)

from app.api.deps import get_admin_user
from app.domains.streams import deps as streams_deps
from app.domains.streams.admin.schemas import (
    ChannelConfig,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
    StreamIngestResponse,
)
from app.domains.streams.admin.service import StreamAdminService
from app.domains.users.models import User

router = APIRouter(prefix="/admin/streams", tags=["스트리밍 관리"])


@router.post(
    "/concerts/{concert_id}/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="콘서트 세션 생성",
    response_model=SessionResponse,
    description="특정 콘서트의 회차를 생성합니다.",
)
async def create_concert_stream(
    concert_id: int = Path(..., description="콘서트 ID"),
    data: SessionCreateRequest = Body(..., description="새로운 콘서트 세션과 IVS config 상세 정보"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    return await service.create_session(concert_id, data, current_admin)


@router.post(
    "/concerts/{concert_id}/sessions/provision",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionResponse,
    summary="기존 세션에 AWS IVS 채널 발급",
)
async def provision_concert_stream(
    session_id: int,
    config: ChannelConfig,
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    """
    1. AWS IVS `CreateChannel` API를 호출하여 송출/재생 엔드포인트를 확보합니다.
    2. 발급된 스트림 키는 내부 보안 정책에 따라 암호화하여 저장합니다.
    """
    return await service.provision_channel(session_id, current_admin, config)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="콘서트 세션 목록 조회",
    description="모든 콘서트 세션을 조회합니다. \
    AWS IVS의 현재 라이브 상태를 실시간으로 확인하여 목록에 반영합니다.",
)
async def list_concert_sessions(
    cursor: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionListResponse:
    return await service.list_sessions_admin(current_admin, limit, cursor)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="콘서트 세션 상세 조회",
)
async def get_concert_session_detail(
    session_id: int = Path(..., description="조회할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    return await service.get_session_admin_detail(session_id, current_admin)


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="콘서트 세션 및 인프라 수정",
    description="세션 정보와 IVS 설정을 부분 수정합니다. \
        channel_config 전달 시 AWS 설정도 즉시 변경됩니다.",
)
async def update_concert_session(
    session_id: int = Path(..., description="수정할 세션 ID"),
    data: SessionUpdateRequest = Body(...),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    return await service.update_session_infrastructure(session_id, data, current_admin)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="콘서트 세션 및 인프라 삭제",
    description="특정 세션을 삭제하고, 연결된 AWS IVS 채널 리소스를 즉시 삭제",
)
async def delete_concert_session(
    session_id: int = Path(..., description="삭제할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> None:
    return await service.delete_session_with_infrastructure(session_id, current_admin)


@router.post(
    "/sessions/{session_id}/rotate-key",
    summary="스트림 키 강제 재발급 (보안)",
    description="기존의 모든 스트림 키를 무효화(삭제)하고 새로운 키 생성 \
                스트림 키가 유출되었을 때 사용합니다.",
)
async def rotate_session_stream_key(
    session_id: int = Path(..., description="키를 갱신할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> dict[str, str]:
    new_key = await service.rotate_stream_key(session_id, current_admin)
    return {"message": "스트림 키가 재발급되었습니다.", "value": new_key}


@router.post(
    "/sessions/{session_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="라이브 방송 강제 종료",
    description="현재 진행 중인 AWS IVS 스트림 송출을 강제 중단시키고, 세션 상태를 'ENDED'로 변경",
)
async def stop_live_stream(
    session_id: int = Path(..., description="중단할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> None:
    await service.stop_stream_session(session_id, current_admin)


@router.patch(
    "/sessions/{session_id}/reopen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="종료된 세션을 재활성화",
    description="ENDED 상태의 세션을 READY 상태로 전환하여 재방송 준비 상태로 만듦",
)
async def reopen_live_stream(
    session_id: int = Path(..., description="재활성화할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> None:
    await service.reopen_session(session_id, current_admin)


# ================================= ivs 송출 테스트용 엔드포인트 =================================
@router.get(
    "/sessions/{session_id}/ingest",
    response_model=StreamIngestResponse,
    summary="송출 정보 조회 (OBS용)",
    description="AWS IVS 채널의 Ingest Endpoint와 복호화된 Stream Key 조회  \
                \n\n 현재 실제 송출 여부와 시청자 수 등 실시간 메트릭을 함께 반환",
)
async def get_session_ingest_data(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> StreamIngestResponse:
    return await service.get_stream_ingest_info(session_id, user=current_admin)
