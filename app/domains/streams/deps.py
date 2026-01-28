from fastapi import Depends

from app.api.deps import get_current_user
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
async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    # 관리자 권한 체크
    StreamPermission.must_be_admin(current_user)
    return current_user
