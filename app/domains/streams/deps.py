from app.domains.streams.service import StreamService
from app.integrations.aws_ivs import IVSClient, IVSPlaybackProvider


def get_ivs_client() -> IVSClient:
    return IVSClient()


def get_playback_provider() -> IVSPlaybackProvider:
    return IVSPlaybackProvider()


def get_streams_service() -> StreamService:
    return StreamService(
        ivs_client=get_ivs_client(),
        playback_provider=get_playback_provider(),
    )
