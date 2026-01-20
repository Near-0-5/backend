import time

import jwt
import pytest

from app.integrations.aws_ivs.playback import IVSPlaybackProvider


@pytest.fixture
def provider() -> IVSPlaybackProvider:
    return IVSPlaybackProvider()


class TestIVSPlaybackProvider:
    # --- IVS 재생 토큰 (ES384) 테스트 ---

    def test_sign_playback_token_success(self, provider: IVSPlaybackProvider):
        # Given
        channel_arn = "arn:aws:ivs:ap-northeast-2:123456789012:channel/test-channel"
        viewer_id = "user_123"

        # When
        token = provider.sign_playback_token(channel_arn, viewer_id)

        # Then
        assert isinstance(token, str)
        # 디코딩 검증 (알고리즘 확인)
        decoded = jwt.decode(token, provider._ivs_private_key, algorithms=["ES384"])
        assert decoded["aws:channel-arn"] == channel_arn
        assert decoded["aws:viewer-id"] == viewer_id
        assert decoded["exp"] > decoded["iat"]

    # --- 내부 세션 토큰 (HS256) 테스트 ---

    def test_sign_internal_tokens(self, provider: IVSPlaybackProvider):
        # Given
        user_id = "user_123"
        stream_id = "stream_456"

        # When
        tokens = provider.sign_internal_tokens(user_id, stream_id)

        # Then
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Access 토큰 내용 검증
        decoded = jwt.decode(tokens["access_token"], provider._secret, algorithms=["HS256"])
        assert decoded["sub"] == user_id
        assert decoded["stream_id"] == stream_id
        assert decoded["type"] == "access"

    def test_verify_internal_token_success(self, provider: IVSPlaybackProvider):
        # Given
        tokens = provider.sign_internal_tokens("u1", "s1")

        # When & Then (정상 케이스)
        payload = provider.verify_internal_token(tokens["access_token"], expected_type="access")
        assert payload["sub"] == "u1"

    def test_verify_internal_token_invalid_type(self, provider: IVSPlaybackProvider):
        # Given (Access 토큰을 넘기면서 Refresh 타입을 기대함)
        tokens = provider.sign_internal_tokens("u1", "s1")

        # When & Then
        with pytest.raises(ValueError, match="토큰 타입 불일치"):
            provider.verify_internal_token(tokens["access_token"], expected_type="refresh")

    def test_verify_internal_token_expired(self, provider: IVSPlaybackProvider):
        # Given - 이미 만료된 토큰을 직접 생성
        past_time = int(time.time()) - (8 * 24 * 3600)  # 8일 전
        expired_payload = {
            "sub": "u1",
            "stream_id": "s1",
            "type": "refresh",
            "iat": past_time,
            "exp": past_time + (7 * 24 * 3600),  # 1일 전에 만료됨
        }
        expired_token = jwt.encode(expired_payload, provider._secret, algorithm="HS256")

        # When & Then
        with pytest.raises(ValueError, match="토큰이 만료되었습니다"):
            provider.verify_internal_token(expired_token, expected_type="refresh")

    # --- 재발급 및 유틸리티 테스트 ---

    def test_refresh_access_token(self, provider: IVSPlaybackProvider):
        # Given
        tokens = provider.sign_internal_tokens("u1", "s1")

        # When
        new_access_token = provider.refresh_access_token(tokens["refresh_token"])

        # Then
        payload = provider.verify_internal_token(new_access_token, expected_type="access")
        assert payload["sub"] == "u1"
        assert payload["stream_id"] == "s1"

    def test_rotate_tokens(self, provider: IVSPlaybackProvider):
        # Given
        old_tokens = provider.sign_internal_tokens("u1", "s1")

        # When
        new_tokens = provider.rotate_tokens(old_tokens["refresh_token"])

        # Then
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # 새 토큰이 유효한지 확인
        decoded = jwt.decode(new_tokens["refresh_token"], provider._secret, algorithms=["HS256"])
        assert decoded["sub"] == "u1"
        assert decoded["stream_id"] == "s1"

    def test_get_internal_token_remaining_time(self, provider: IVSPlaybackProvider):
        # Given
        tokens = provider.sign_internal_tokens("u1", "s1")

        # When
        remaining = provider.get_internal_token_remaining_time(tokens["access_token"])

        # Then (기본 30분 설정이므로 약 1800초 내외)
        assert 1700 < remaining <= 1800
