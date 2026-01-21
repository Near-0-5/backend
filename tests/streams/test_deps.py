from app.domains.streams import deps


def test_get_ivs_client():
    """IVS Client 생성 테스트"""
    client = deps.get_ivs_client()
    assert client is not None
    assert hasattr(client, "create_channel")


def test_get_playback_provider():
    """Playback Provider 생성 테스트"""
    provider = deps.get_playback_provider()
    assert provider is not None
    assert hasattr(provider, "sign_playback_token")


def test_get_stream_admin_service():
    """Admin Service DI 테스트"""
    service = deps.get_stream_admin_service()
    assert service is not None
    assert service.ivs_client is not None


def test_get_stream_user_service():
    """User Service DI 테스트"""
    service = deps.get_stream_user_service()
    assert service is not None
    assert service.ivs_client is not None
    assert service.playback_provider is not None
