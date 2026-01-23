from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user, get_user_from_refresh_token
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.client.service import StreamUserService
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


def get_ivs_client() -> IVSClient:
    return IVSClient()


def get_playback_provider() -> IVSPlaybackProvider:
    return IVSPlaybackProvider()


# Admin 전용 서비스 주입
def get_stream_admin_service(
    ivs: IVSClient = Depends(get_ivs_client),
    provider: IVSPlaybackProvider = Depends(get_playback_provider),
) -> StreamAdminService:
    return StreamAdminService(ivs_client=ivs, playback_provider=provider)


# User 전용 서비스 주입
def get_stream_user_service(
    ivs: IVSClient = Depends(get_ivs_client),
    provider: IVSPlaybackProvider = Depends(get_playback_provider),
) -> StreamUserService:
    return StreamUserService(ivs_client=ivs, playback_provider=provider)


# 어드민 유저
async def get_admin_user(
    request: Request,
) -> User:
    user = None

    # Authorization 헤더(Access Token)가 있는지 확인
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            user = await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_header.split(" ")[1])
            )
        except HTTPException:
            user = None

    # 헤더에 없다면 쿠키(Refresh Token) 확인
    if not user:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            user = await get_user_from_refresh_token(refresh_token)

    # 둘 다 없다면 에러 발생
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 없습니다. (Access Token 또는 Refresh Token 필요)",
        )

    # 관리자 권한 체크
    StreamPermission.must_be_admin(user)
    return user
