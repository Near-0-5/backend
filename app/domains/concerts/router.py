from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import get_admin_user
from app.domains.concerts import deps as concerts_deps
from app.domains.concerts.models import Concert
from app.domains.concerts.schemas import (
    ConcertCreateRequest,
    ConcertDetailResponse,
    ConcertResponse,
)
from app.domains.concerts.service import ConcertAdminService
from app.domains.users.models import User

router = APIRouter(prefix="/admin/concerts", tags=["콘서트 관리"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ConcertResponse,
    summary="콘서트 메타정보 생성",
    description="신규 콘서트의 기본 메타데이터(제목, 카테고리 등)를 생성합니다. \
    인프라 리소스는 생성되지 않습니다.",
)
async def create_concert(
    data: ConcertCreateRequest,
    current_admin: User = Depends(get_admin_user),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> Concert:
    return await service.create_concert(data, current_admin)


@router.get(
    "",
    response_model=list[ConcertResponse],
    summary="콘서트 목록 조회",
)
async def list_concerts(
    response: Response,
    cursor: int | None = Query(None, description="마지막으로 조회된 콘서트 ID"),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_admin_user),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> list[Concert]:
    concerts, next_cursor = await service.list_concerts(current_admin, limit, cursor)

    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = str(next_cursor)
    return concerts


@router.get(
    "/{concert_id}",
    response_model=ConcertDetailResponse,
    summary="콘서트 상세 조회",
)
async def get_concert_detail(
    concert_id: int = Path(..., description="콘서트 ID"),
    current_admin: User = Depends(get_admin_user),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> ConcertDetailResponse:
    return await service.get_concert_detail(concert_id, current_admin)


@router.patch(
    "/{concert_id}",
    response_model=ConcertResponse,
    summary="콘서트 정보 수정",
)
async def update_concert(
    concert_id: int = Path(...),
    data: ConcertCreateRequest = Body(...),
    current_admin: User = Depends(get_admin_user),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> Concert:
    return await service.update_concert(concert_id, data, current_admin)


@router.delete(
    "/{concert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="콘서트 및 관련 인프라 전체 삭제",
)
async def delete_concert(
    concert_id: int = Path(...),
    current_admin: User = Depends(get_admin_user),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> None:
    return await service.delete_concert_with_infrastructure(concert_id, current_admin)


@router.patch(
    "/{concert_id}/thumbnail",
    response_model=ConcertResponse,
    summary="콘서트 썸네일 이미지 생성 및 수정",
    description="콘서트 썸네일 이미지를 업로드 또는 수정합니다.",
)
async def update_concert_thumbnail(
    current_admin: User = Depends(get_admin_user),
    concert_id: int = Path(..., description="콘서트 ID"),
    thumbnail_file: UploadFile = File(..., description="썸네일 이미지 파일"),
    service: ConcertAdminService = Depends(concerts_deps.get_concert_admin_service),
) -> Concert:
    # 인증된 current_admin 객체를 서비스로 직접 전달
    return await service.update_concert_thumbnail(
        concert_id=concert_id, file=thumbnail_file, user=current_admin
    )
