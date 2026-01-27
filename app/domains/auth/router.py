from http.client import HTTPException
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_from_refresh_cookie  # 유저 인증 의존성
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.domains.auth.schemas import TokenResponse
from app.domains.auth.service import auth_service
from app.domains.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
@router.post("/login-test", summary="[개발용] 로그인")
async def admin_login(
    response: Response,
    user_id: int = Query(..., description="어드민 1  |  유저 2"),
) -> dict[str, Any]:
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(404, "User not found")
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # 자바스크립트 접근 방지 (보안)
        samesite="lax",  # CSRF 방지
        secure=True,  # HTTPS에서 활성화
        max_age=60 * 60 * 24 * 7,  # 7일간 유지
    )

    return {
        "is_admin": user.is_superuser,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "message": "쿠키가 성공적으로 설정되었습니다.",
    }


# ============================================================


@router.get("/kakao/login", summary="카카오 서비스 로그인")
async def kakao_login() -> RedirectResponse:
    """
    카카오 로그인 페이지로 리다이렉트됩니다.
    """
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )
    return RedirectResponse(kakao_auth_url)


@router.get("/kakao/callback", include_in_schema=False)
async def kakao_callback(response: Response, code: str = Query(...)) -> RedirectResponse:
    """
    카카오 인증 서버로부터 리다이렉트되어 인가 코드를 받습니다.
    settings.CALLBACK_REDIRECT_URL 리다이렉트합니다.
    사용자가 직접 호출할 필요가 없으므로 API 문서에서 제외합니다.
    """
    token_data = await auth_service.process_kakao_login(code)

    # 화면으로 보낼 redirect url 구성 및 응답할 RedirectResponse 설정
    redirect_url = (
        f"{settings.CALLBACK_REDIRECT_URL}"
        f"?access_token={token_data.access_token}"
        f"&is_new_user={str(token_data.is_new_user).lower()}"
    )
    redirect_response = RedirectResponse(url=redirect_url)

    # Refresh Token을 HttpOnly 쿠키에 설정
    redirect_response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=True,  # HTTPS에서만 작동 True
        samesite="lax",
        path="/",  # 삭제할거면 전체에서 삭제
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,  # 7 * 24 * 60* 60
    )

    return redirect_response


@router.post("/logout", summary="로그아웃", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    """쿠키를 삭제하여 로그아웃 처리"""
    await auth_service.logout_user(response)

    response.status_code = status.HTTP_204_NO_CONTENT
    return response  # 쿠키 설정을 그대로 유지


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    # 쿠키에서 직접 리프레시 토큰을 가져와 jwt 검증
    current_user: User = Depends(get_current_user_from_refresh_cookie),
) -> TokenResponse:
    token_data = await auth_service.refresh_access_token(current_user.id)

    # 새로운 리프레시 토큰 쿠키 갱신
    response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,  # 7 * 24 * 60* 60
    )
    return token_data
