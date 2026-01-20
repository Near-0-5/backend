from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.domains.auth.schemas import TokenResponse
from app.domains.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.get("/kakao/callback", response_model=TokenResponse, include_in_schema=False)
async def kakao_callback(code: str = Query(...)) -> TokenResponse:
    """
    카카오 인증 서버로부터 리다이렉트되어 인가 코드를 받습니다.
    사용자가 직접 호출할 필요가 없으므로 API 문서에서 제외합니다.
    """
    return await auth_service.process_kakao_login(code)
