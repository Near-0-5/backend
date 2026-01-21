from app.domains.streams.service import StreamAdminService, StreamUserService
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
