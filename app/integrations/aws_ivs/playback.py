import time
from typing import Any, Literal, TypedDict, cast

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


# --- JWT 페이로드 정의 (Type Hinting) ---
class IVSPlaybackPayload(TypedDict):
    """AWS IVS 공식 Playback Token 규격 (ES384)"""

    iat: int  # Issued At (언제 발급)
    exp: int  # Expiration Time (언제 만료)
    # "aws:channel-arn": str
    # "aws:viewer-id": str


class InternalTokenPayload(TypedDict):
    """우리 서비스 내부 인증용 페이로드 (HS256)"""

    sub: str  # User ID
    stream_id: str  # 방송 PK
    type: Literal["access", "refresh"]
    iat: int
    exp: int


class IVSPlaybackProvider:
    """
    AWS IVS 재생 토큰 및 내부 세션 토큰의 생명주기를 관리하는 프로바이더
    """

    def __init__(self) -> None:
        self._secret = settings.SECRET_KEY
        self._ivs_private_key = settings.IVS_PLAYBACK_PRIVATE_KEY
        self._algo_internal = "HS256"
        self._algo_ivs = "ES384"

    # ===================== playback_token 발급 =====================

    def sign_playback_token(
        self, channel_arn: str, viewer_id: str, duration_sec: int = 3600
    ) -> str:
        """
        [IVS 전용] 비공개 채널 시청 토큰 발급 (ES384 서명)
        - Playback URL 뒤에 '?token=' 파라미터로 붙음
        - 재생 세션보다 짧은 TTL
        """
        if not self._ivs_private_key:
            raise RuntimeError("IVS_PLAYBACK_PRIVATE_KEY가 설정되지 않았습니다.")

        now = int(time.time())
        payload = {
            "aws:channel-arn": channel_arn,
            "aws:viewer-id": viewer_id,
            "iat": now,
            "exp": now + duration_sec,
        }
        # ECDSA P-384 알고리즘으로 서명
        return jwt.encode(payload, self._ivs_private_key, algorithm=self._algo_ivs)

    def sign_internal_tokens(self, user_id: str, stream_id: str) -> dict[str, str]:
        """
        [내부 세션] Access & Refresh 토큰 세트 발급 (HS256)
        - Access: 채팅/API 접근용 (단기)
        - Refresh: 토큰 재발급용 (장기)
        """
        now = int(time.time())

        access_exp = now + (30 * 60)  # 30분
        refresh_exp = now + (7 * 24 * 3600)  # 7일

        def _encode(payload: dict[str, Any]) -> str:
            return jwt.encode(payload, self._secret, algorithm=self._algo_internal)

        return {
            "access_token": _encode(
                {
                    "sub": user_id,
                    "stream_id": stream_id,
                    "type": "access",
                    "iat": now,
                    "exp": access_exp,
                }
            ),
            "refresh_token": _encode(
                {
                    "sub": user_id,
                    "stream_id": stream_id,
                    "type": "refresh",
                    "iat": now,
                    "exp": refresh_exp,
                }
            ),
        }

    # ===================== playback_token 검증 =====================

    def verify_internal_token(
        self, token: str, expected_type: Literal["access", "refresh"]
    ) -> InternalTokenPayload:
        """
        [내부 세션] 토큰의 기술적 유효성 및 타입을 검증
        - 서명 위조, 만료 여부, 토큰 용도(access/refresh) 확인
        """
        try:
            decoded = jwt.decode(token, self._secret, algorithms=[self._algo_internal])
            payload = cast("InternalTokenPayload", decoded)

            if payload.get("type") != expected_type:
                raise ValueError(f"토큰 타입 불일치: {expected_type} 필요")

            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("토큰이 만료되었습니다.") from None
        except InvalidTokenError as e:
            raise ValueError(f"유효하지 않은 토큰입니다: {str(e)}") from e

    # ===================== playback_token 재발급 =====================

    def rotate_tokens(self, refresh_token: str) -> dict[str, str]:
        """
        [내부 세션] Access와 Refresh 토큰을 모두 새로 발급 (Refresh Token Rotation)
        """
        payload = self.verify_internal_token(refresh_token, expected_type="refresh")
        # 기존 페이로드 정보를 바탕으로 새 토큰(Access + Refresh) 발급
        return self.sign_internal_tokens(user_id=payload["sub"], stream_id=payload["stream_id"])

    # ===================================================

    def get_internal_token_remaining_time(self, token: str) -> int:
        """
        [Internal Token 전용] 만료까지 남은 시간(초)
        """
        try:
            decoded = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algo_internal],
                options={"verify_exp": False},
            )
            exp = decoded.get("exp")
            if not isinstance(exp, int):
                return 0
            return max(0, exp - int(time.time()))
        except InvalidTokenError:
            return 0
