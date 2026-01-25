from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path
from fastapi.params import Query

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.client.schemas import (
    SessionDetailResponse,
    SessionItem,
    SessionListResponse,
)
from app.domains.streams.client.service import StreamUserService
from app.domains.streams.models import CategoryType, StreamStatus
from app.domains.users.models import User

router = APIRouter(prefix="/streams", tags=["Streaming"])


@router.get(
    "/sessions/{session_id}/credentials",
    summary="스트림 시청 권한 확인 - 토큰 발급",
    description="실시간 스트리밍 시청을 위한 Playback URL과 인증 토큰을 발급합니다. \
                \n\n 비공개 채널의 경우 IVS Playback Token이 포함됩니다.",
)
async def get_stream_access(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    current_user: User = Depends(deps.get_current_user),
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> dict[str, Any]:
    """
    1. 유저의 세션 시청 자격(티켓 등)을 검증합니다.
    2. AWS IVS 채널 설정에 따라 Playback Token 서명 여부를 결정합니다.
    3. 채팅 서버 인증을 위한 내부 세션 토큰을 함께 반환합니다.
    """
    return await service.get_viewing_credentials(session_id, current_user)


@router.post(
    "/sessions/{session_id}/refresh",
    summary="시청 세션 연장 (토큰 재발급)",
    description="시청 중 토큰이 만료되기 전, 기존 리프레시 토큰을 사용해 세션을 연장합니다. \
                 \n\n 이때 유저의 시청 자격을 재검증합니다.",
)
async def refresh_stream_session(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    refresh_token: str = Body(..., embed=True),  # json body에서 refresh_token 추출
    current_user: User = Depends(deps.get_current_user),
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> dict[str, Any]:
    """
    1. 유저의 리프레시 토큰을 검증하고 새로운 Access/Refresh 토큰 세트를 생성합니다.
    2. 동시에 새로운 유효기간을 가진 AWS IVS 재생 토큰을 발급받아 반환합니다.
    """
    return await service.refresh_viewing_session(
        session_id,
        current_user,
        refresh_token,
    )


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="스트리밍 목록 조회",
)
async def list_sessions(
    status: StreamStatus | None = None,
    category: CategoryType | None = None,
    artist_name: Annotated[
        str | None, Query(description="검색: 출연진 이름 (부분 검색 가능)")
    ] = None,
    title: Annotated[str | None, Query(description="검색: 공연 이름 (부분 검색 가능)")] = None,
    from_date: Annotated[
        date | None, Query(description="시작 날짜가 해당 날짜 이후 (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[
        date | None, Query(description="종료 날짜가 해당 날짜까지 (YYYY-MM-DD)")
    ] = None,
    order_by: Annotated[
        str, Query(description="정렬 순서: latest (최신순), oldest (과거순)")
    ] = "latest",
    cursor: Annotated[
        int | None, Query(description="커서 페이지네이션용 기준 ID (이전 응답의 next_cursor)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="페이지당 조회 개수")] = 10,
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> SessionListResponse:
    items, next_cursor = await service.list_sessions(
        status=status,
        category=category,
        artist_name=artist_name,
        title=title,
        from_date=from_date,
        to_date=to_date,
        order_by=order_by,
        cursor=cursor,
        limit=limit,
    )

    return SessionListResponse(
        items=[
            SessionItem.model_validate(
                {
                    **s.__dict__,
                    "concert_title": s.concert.title,
                    "thumbnail_url": s.concert.thumbnail_url,
                    "category": s.concert.category,
                }
            )
            for s in items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/sessions/{session_id}", response_model=SessionDetailResponse, summary="공연 상세 정보 조회"
)
async def get_session_detail(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    current_user: User = Depends(deps.get_current_user),
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> SessionDetailResponse:
    return await service.get_sessions_detail(current_user, session_id)
