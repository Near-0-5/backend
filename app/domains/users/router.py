from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user
from app.domains.users.models import User
from app.domains.users.schemas import UserMeResponse
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
) -> dict[str, Any]:
    """내 프로필 정보를 반환합니다."""
    return await user_service.get_user_profile(current_user.id)


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
