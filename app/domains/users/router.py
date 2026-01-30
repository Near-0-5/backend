from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, File, Response, UploadFile, status

from app.api.deps import get_current_user
from app.domains.users.models import User
from app.domains.users.schemas import (
    FavoriteArtistCreate,
    FavoriteArtistListResponse,
    FavoriteArtistResponse,
    UserMeResponse,
    UserMeUpdate,
)
from app.domains.users.service import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 조회",
    description="""
    현재 로그인한 사용자의 상세 정보를 조회합니다.
    - **기본 정보**: 이메일, 닉네임, 실명, 프로필 이미지 등
    - **활동 정보**: 팔로우 중인 아티스트 리스트
    - **설정 정보**: 선호 카테고리 및 개인화된 알림 설정 상태
    """,
    responses={
        401: {"description": "인증되지 않은 사용자 (토큰 만료 또는 누락)"},
        404: {"description": "사용자 정보를 찾을 수 없음"},
    },
)
async def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserMeResponse:
    """내 프로필 정보를 반환합니다."""
    return await user_service.get_user_profile(current_user.id)


@router.patch(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 수정",
    description="로그인한 회원의 닉네임, 프로필 이미지, 알림 설정, 자기소개를 수정합니다.",
)
async def update_my_profile(
    current_user: Annotated[User, Depends(get_current_user)], data: UserMeUpdate = Body(...)
) -> Any:
    """회원 정보를 수정하고 업데이트된 정보를 반환합니다."""

    return await user_service.update_user_profile(current_user, data)


@router.delete("/me", summary="회원 탈퇴", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw(
    response: Response,
    current_user: User = Depends(get_current_user),
    reason: str = "사용자 요청에 의한 탈퇴",
) -> Response:
    """회원 데이터 삭제 및 쿠키 제거"""
    # DB 삭제
    await user_service.withdraw_kakao_user(current_user, reason)
    # 쿠키제거
    response.delete_cookie(key="refresh_token", path="/")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/image", summary="프로필 이미지 업로드")
async def upload_my_profile_image(
    current_user: Annotated[User, Depends(get_current_user)], file: UploadFile = File(...)
) -> UserMeResponse:
    return await user_service.update_profile_image(current_user, file)


@router.get(
    "/me/favorite-artists",
    response_model=FavoriteArtistListResponse,
    summary="사용자의 선호 아티스트 목록 조회",
)
async def get_my_favorite_artists(
    current_user: User = Depends(get_current_user),
) -> FavoriteArtistListResponse:
    """
    현재 로그인한 유저가 팔로우 중인 아티스트 목록을 반환합니다.
    """
    return await user_service.get_favorite_artists(current_user)


@router.post(
    "/me/favorite-artists",
    response_model=FavoriteArtistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="선호 아티스트 추가",
    description="로그인한 사용자가 특정 아티스트를 팔로우 목록에 추가합니다.",
)
async def add_my_favorite_artist(
    data: FavoriteArtistCreate, current_user: User = Depends(get_current_user)
) -> FavoriteArtistResponse:
    return await user_service.add_follow_artist(current_user, data)


@router.delete(
    "/me/favorite-artists/{artist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자의 선호 아티스트 삭제",
    description="현재 로그인한 사용자가 팔로우 중인 특정 아티스트를 목록에서 삭제합니다.",
    responses={
        204: {"description": "삭제 성공"},
        401: {"description": "인증되지 않은 사용자"},
        404: {"description": "팔로우 중인 아티스트(ID: {artist_id})를 찾을 수 없습니다."},
    },
)
async def unfollow_artist(
    artist_id: int,
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    선호 아티스트(팔로우)를 취소합니다.
    """
    return await user_service.remove_follow_artist(current_user, artist_id)
