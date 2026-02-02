from fastapi import Depends

from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.client.service import StreamUserService
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
