import time
from typing import TypedDict

import jwt

from app.core.config import settings


# --- JWT 페이로드 정의 (Type Hinting) ---
class IVSPlaybackPayload(TypedDict):
    """AWS IVS 공식 Playback Token 규격 (ES384)"""

    iat: int  # Issued At (언제 발급)
    exp: int  # Expiration Time (언제 만료)
    # "aws:channel-arn": str
    # "aws:viewer-id": str


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
