import time

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

    def test_internal_token_full_cycle(self, provider):
        # 토큰 발급
        tokens = provider.sign_internal_tokens("user1", "stream1")

        # 검증 (정상)
        payload = provider.verify_internal_token(tokens["access_token"], expected_type="access")
        assert payload["sub"] == "user1"

        # 토큰 타입 불일치 에러
        with pytest.raises(ValueError, match="토큰 타입 불일치"):
            provider.verify_internal_token(tokens["access_token"], expected_type="refresh")

        # 만료된 토큰 처리
        expired_payload = {
            "sub": "u",
            "stream_id": "s",
            "type": "access",
            "iat": int(time.time()) - 4000,
            "exp": int(time.time()) - 1000,
        }
        expired_token = jwt.encode(expired_payload, provider._secret, algorithm="HS256")
        with pytest.raises(ValueError, match="토큰이 만료되었습니다"):
            provider.verify_internal_token(expired_token, "access")

        # 유효하지 않은 토큰
        with pytest.raises(ValueError, match="유효하지 않은 토큰입니다"):
            provider.verify_internal_token("invalid.token.here", "access")

        # 토큰 재발급
        time.sleep(1.1)  # iat 변경 보장
        new_tokens = provider.rotate_tokens(tokens["refresh_token"])
        assert tokens["access_token"] != new_tokens["access_token"]

        # 남은 시간 조회
        rem = provider.get_internal_token_remaining_time(tokens["access_token"])
        assert 1700 < rem <= 1800
        assert provider.get_internal_token_remaining_time("wrong") == 0
