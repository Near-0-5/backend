from typing import Any, cast

import httpx

from app.core.config import settings


class NaverIntegration:
    TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
    USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"

    def __init__(self) -> None:
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.redirect_uri = settings.NAVER_REDIRECT_URI
        # 성능을 위해 단일 클라이언트 사용 (필요시 lifespan에서 관리)
        self.client = httpx.AsyncClient()

    async def get_access_token(self, code: str, state: str = "naver_login") -> str:
        """인가 코드로 네이버 액세스 토큰 획득"""
        response = await self.client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "state": state,
            },
        )
        response.raise_for_status()
        result = response.json()
        return str(result.get("access_token", ""))

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """액세스 토큰으로 네이버 유저 프로필 조회"""
        response = await self.client.get(
            self.USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        # 네이버는 응답 데이터가 'response' 키 안에 묶여서 온다.
        return cast("dict[str, Any]", response.json().get("response", {}))


# 싱글톤 인스턴스 생성
naver_client = NaverIntegration()
