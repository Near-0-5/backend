from typing import Any, cast

import httpx

from app.core.config import settings


class KakaoIntegration:
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"

    def __init__(self) -> None:
        self.client_id = settings.KAKAO_REST_API_KEY
        self.redirect_uri = settings.KAKAO_REDIRECT_URI
        self.client_secret = settings.KAKAO_CLIENT_SECRET
        # 생성/해제의 반복으로 인한 성능 저하 방지.
        self.client = httpx.AsyncClient()  # 생성/해제가 반복되어 성능 저하

    # 토큰을 받아온다.
    async def get_access_token(self, code: str) -> str:
        response = await self.client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code": code,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response.raise_for_status()

        result = response.json().get("access_token")
        return str(result) if result else ""

    # 유저 정보를 받아온다.
    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        response = await self.client.get(
            self.USER_INFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())


kakao_client = KakaoIntegration()
