from fastapi import APIRouter, Query

from app.domains.auth.schemas import TokenResponse
from app.domains.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/kakao/callback", response_model=TokenResponse)
async def kakao_callback(code: str = Query(...)) -> TokenResponse:
    return await auth_service.process_kakao_login(code)
