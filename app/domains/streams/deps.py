from fastapi import Depends

from app.api.deps import get_current_user_from_refresh_cookie
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.client.service import StreamUserService
from app.domains.streams.permissions import StreamPermission
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


def get_ivs_client() -> IVSClient:
    return IVSClient()


def get_playback_provider() -> IVSPlaybackProvider:
    return IVSPlaybackProvider()


# 1. Admin 전용 서비스 주입
def get_stream_admin_service() -> StreamAdminService:
    return StreamAdminService(ivs_client=get_ivs_client())


# 2. User 전용 서비스 주입
def get_stream_user_service() -> StreamUserService:
    return StreamUserService(
        ivs_client=get_ivs_client(),  # 채널 조회용
        playback_provider=get_playback_provider(),  # 토큰 발행용
    )


# 어드민 유저
async def get_admin_user(
    current_user: User = Depends(get_current_user_from_refresh_cookie),
) -> User:
    StreamPermission.must_be_admin(current_user)
    return current_user
