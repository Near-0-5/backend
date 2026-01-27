import jwt
import pytest

from app.integrations.aws_ivs.playback import IVSPlaybackProvider


@pytest.fixture
def provider():
    return IVSPlaybackProvider()


class TestIVSPlaybackProvider:
    def test_sign_playback_token(self, provider):
        # IVS Playback Token 생성 및 규격 확인
        token = provider.sign_playback_token("arn:aws:ivs:test", "viewer1")
        decoded = jwt.decode(token, provider._ivs_private_key, algorithms=["ES384"])
        assert decoded["aws:channel-arn"] == "arn:aws:ivs:test"
        assert decoded["aws:viewer-id"] == "viewer1"
