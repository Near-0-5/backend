from enum import Enum

from fastapi import APIRouter, Query, status

from app.domains.artists.schemas import ArtistDetailResponse, ArtistListResponse
from app.domains.artists.service import artist_service

router = APIRouter(prefix="/artists", tags=["artists"])


class ArtistSortOrder(str, Enum):
    LATEST = "latest"  # 최신 등록순
    FOLLOWER = "follower"  # 팔로워 많은 순
    NAME = "name"  # 이름 가나다순


@router.get(
    "",
    response_model=ArtistListResponse,
    status_code=status.HTTP_200_OK,
    summary="아티스트 목록 조회",
    description="시스템에 등록된 아티스트 목록을 페이징하여 조회합니다. "
    "검색은 그룹명으로만 가능합니다.",
)
async def get_artist_list(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="한 페이지에 표시할 아티스트 수"),
    search: str | None = Query(None, description="검색할 그룹명 (일부 일치 가능)"),
    category: str | None = Query(None, description="필터링할 카테고리 명칭"),
    sort_by: ArtistSortOrder = Query(ArtistSortOrder.LATEST, description="정렬 기준"),
) -> ArtistListResponse:
    """
    아티스트 목록을 조회합니다.
    - search: 현재 요구사항에 따라 '그룹명(stage_name)'으로만 필터링됩니다.
    - category: 특정 장르나 카테고리에 속한 아티스트만 필터링합니다.
    - follower_count: 각 아티스트의 실시간 팔로우 수가 포함되어 반환됩니다.
    """
    return await artist_service.get_artists(
        page=page, page_size=page_size, search=search, category=category, sort_by=sort_by
    )


@router.get(
    "/{artist_id}",
    response_model=ArtistDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="아티스트 상세 조회",
)
async def get_artist_detail(
    artist_id: int,  # Path Parameter
) -> ArtistDetailResponse:
    """
    특정 아티스트의 상세 정보를 조회합니다.
    """
    return await artist_service.get_artist_detail(artist_id=artist_id)
