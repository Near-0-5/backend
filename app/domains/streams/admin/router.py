from fastapi import APIRouter, Body, Depends, Path, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.domains.streams import deps as streams_deps
from app.domains.streams.admin.schemas import (
    ConcertCreateRequest,
    ConcertResponse,
    SessionCreateRequest,
    SessionResponse,
    StreamIngestResponse,
)
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.deps import get_admin_user
from app.domains.streams.models import Concert
from app.domains.users.models import User

router = APIRouter(prefix="/admin/streams", tags=["[Admin] Streaming"])
templates = Jinja2Templates(directory="templates")


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
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> Concert:
    return await service.create_concert(data, current_admin)


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
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> SessionResponse:
    """
    1. 콘서트 회차(Session) 레코드를 생성합니다.
    2. AWS IVS `CreateChannel` API를 호출하여 송출/재생 엔드포인트를 확보합니다.
    3. 발급된 스트림 키는 내부 보안 정책에 따라 암호화하여 저장합니다.
    """
    return await service.create_session_with_infrastructure(concert_id, data, current_admin)


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
    summary="라이브 방송 강제 종료",
    description="현재 진행 중인 AWS IVS 스트림 송출을 강제 중단시키고, 세션 상태를 'ENDED'로 변경",
)
async def stop_live_stream(
    session_id: int = Path(..., description="중단할 세션 ID"),
    current_admin: User = Depends(get_admin_user),
    service: StreamAdminService = Depends(streams_deps.get_stream_admin_service),
) -> dict[str, str]:
    await service.stop_stream_session(session_id, current_admin)
    return {"message": "방송이 종료 처리되었습니다."}


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


@router.get(
    "/sessions/{session_id}/monitor",
    response_class=HTMLResponse,
    summary="실시간 송출 모니터링 페이지",
    description="관리자가 방송 송출 상태를 확인하고 \
    실시간으로 영상을 프리뷰 할 수 있는 HTML 대시보드",
)
async def stream_monitor_page(
    request: Request,
    session_id: int = Path(..., description="모니터링할 콘서트 세션 ID"),
    current_admin: User = Depends(get_admin_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "stream_monitor.html",
        {"request": request, "session_id": session_id, "is_admin": current_admin.is_superuser},
    )
