from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from fastapi import HTTPException

from app.core.config import settings

ALGORITHM = "HS256"
COGNITO_ALGORITHM = "RS256"  # AWS Cognito용

# JWKS 캐싱용 변수
_jwks_cache = None


async def verify_cognito_token(token: str):
    """
    AWS Cognito ID Token을 검증하고 페이로드를 반환합니다.
    """
    global _jwks_cache
    try:
        # JWKS 가져오기 및 캐싱
        if _jwks_cache is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.COGNITO_JWKS_URL)
                _jwks_cache = response.json()

        # 토큰 헤더에서 kid(Key ID) 추출
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # 3. JWKS에서 kid와 일치하는 공개키 찾기
        key_data = next((k for k in _jwks_cache["keys"] if k["kid"] == kid), None)
        if not key_data:
            raise HTTPException(status_code=401, detail="Invalid token: kid not found")

        # 4. PyJWT는 JWK 객체를 직접 처리하므로 RS256 공개키로 변환 (RSA 공개키 객체 생성)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

        # 5. 토큰 검증 및 디코딩
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[COGNITO_ALGORITHM],
            audience=settings.COGNITO_CLIENT_ID,
            issuer=f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}",
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    엑세스 토큰을 생성합니다.
    15~ 60분간 유효합니다.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}  # 타입추가
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    """
    리프레시 토큰을 생성합니다.
    유효기간은 7일입니다.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
