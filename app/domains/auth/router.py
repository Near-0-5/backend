import secrets
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_from_refresh_cookie, logger  # 유저 인증 의존성
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.domains.auth.schemas import TokenResponse
from app.domains.auth.service import auth_service
from app.domains.users.models import ProviderChoice, User

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
        samesite="none",
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


@router.get("/login", summary="소셜 로그인 시작 (Cognito 호스팅 UI)")
async def social_login(
    response: Response, provider: ProviderChoice = ProviderChoice.KAKAO
) -> RedirectResponse:
    """
    카카오, 구글은 Cognito로, 네이버는 네이버 직접 로그인으로 리다이렉트합니다.
    """
    # 입력된 값을 첫글자 대문자로 변환 (naver -> Naver, NAVER -> Naver)
    formatted_provider = provider.capitalize()

    # 네이버
    if formatted_provider == ProviderChoice.NAVER:
        # 네이버는 Cognito를 거치지 않고 직접 네이버 API로 보냅니다.
        state = secrets.token_urlsafe(32)
        naver_login_url = (
            "https://nid.naver.com/oauth2.0/authorize"
            f"?response_type=code"
            f"&client_id={settings.NAVER_CLIENT_ID}"
            f"&redirect_uri={settings.NAVER_REDIRECT_URI}"  # 네이버 전용 콜백 필요
            f"&state={state}"
        )
        redirect_response = RedirectResponse(naver_login_url)

        # 검증을 위해 state 값을 브라우저 쿠키에 임시 저장 (3분만 유지)
        redirect_response.set_cookie(
            key="naver_state",
            value=state,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=180,  # 3분 내에 로그인을 완료해야 함
            path="/",
        )
        return redirect_response

    # 구글, 카카오
    cognito_login_url = (
        f"{settings.COGNITO_DOMAIN}/oauth2/authorize"
        f"?client_id={settings.COGNITO_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&redirect_uri={settings.COGNITO_REDIRECT_URI}"
        f"&identity_provider={provider.value}"
    )
    return RedirectResponse(cognito_login_url)


@router.get("/cognito/callback", include_in_schema=False, summary="소셜 로그인 공용 콜백")
async def social_callback(response: Response, code: str = Query(...)) -> RedirectResponse:
    """
    Cognito로부터 인가 코드를 받아 process_cognito_login을 실행합니다.
    사용자가 직접 호출할 필요가 없으므로 API 문서에서 제외합니다.
    """
    token_data = await auth_service.process_cognito_login(code)

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
        samesite="none",  # 프론트와의 도메인이 다르기에 none
        path="/",  # 삭제할거면 전체에서 삭제
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,  # 7 * 24 * 60* 60
    )

    return redirect_response


@router.get("/naver/callback", include_in_schema=False, summary="네이버 로그인 공용 콜백")
async def naver_callback(
    response: Response,
    code: str = Query(..., description="네이버 인가 코드"),
    state: str = Query(None, description="CSRF 방지용 상태 값"),
    naver_state: str = Cookie(None, description="우리가 쿠키에 저장한 상태 값"),
) -> RedirectResponse:
    """
    네이버 직접 로그인 콜백 핸들러
    토큰 교환 -> 프로필 조회 -> DB 저장 -> JWT 발급
    """
    # state 검증 수행
    if not state or not naver_state or state != naver_state:
        logger.warning(f"State 불일치: naver_state={naver_state}, state={state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비정상적인 접근입니다. (State mismatch)",
        )
    token_data = await auth_service.process_naver_login(code=code, state=state)

    # 프론트엔드로 리다이렉트 (기존 카카오/구글 콜백과 동일)
    redirect_url = (
        f"{settings.CALLBACK_REDIRECT_URL}?access_token={token_data.access_token}"
        f"&is_new_user={str(token_data.is_new_user).lower()}"
    )
    redirect_response = RedirectResponse(url=redirect_url)

    # 검증 완료된 임시 쿠키 삭제
    redirect_response.delete_cookie("naver_state")

    # refresh Token을 HttpOnly 쿠키에 설정
    redirect_response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
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
        samesite="none",  # 프론트와의 도메인이 다르기에 none
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,  # 7 * 24 * 60* 60
    )
    return token_data
