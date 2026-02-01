from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, WebSocket, status
from fastapi.exceptions import WebSocketException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import ALGORITHM
from app.core.utils.permissions import AdminPermission
from app.core.security import ALGORITHM, verify_cognito_token
from app.domains.users.models import User

security = HTTPBearer()


async def get_current_user_by_cognito(
    auth: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """
    헤더의 Cognito ID Token을 검증하여 유저를 반환합니다.
    (자체 JWT 대신 Cognito 토큰을 직접 쓸 때 사용
    create_access_token으로 직접 만든 토큰을 검증할 때는
    기존의 get_current_user를 사용)
    """
    token = auth.credentials  # 헤더의 Bearer 토큰

    try:
        # Cognito 토큰 검증 (RS256)
        payload = await verify_cognito_token(token)

        # 페이로드에서 고유 식별자(sub) 추출
        cognito_sub = payload.get("sub")
        if not cognito_sub:
            raise HTTPException(status_code=401, detail="Token payload missing 'sub'")

    except Exception as e:
        # 검증 실패 시 401 에러 반환
        raise HTTPException(status_code=401, detail=f"Invalid Cognito token: {str(e)}")

        # DB에서 해당 provider_id(sub)를 가진 유저 조회
    user = await User.get_or_none(provider_id=cognito_sub)
    if not user:
        raise HTTPException(
            status_code=404, detail="Cognito로 인증되었으나 DB에 등록되지 않은 유저입니다"
        )

    return user


async def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """
    현재 로그인 유저를 반환합니다.
    """
    token = auth.credentials  # access_token

    try:
        # payload를 풀어서 정보를 가져온다.
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 유저 정보가 없습니다.",
            )
    except InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 유효하지 않습니다.",
        ) from err

    # DB에서 유저 조회한다.
    user = await User.get_or_none(id=int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 유저입니다."
        )

    return user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    현재 로그인 어드민 유저를 반환합니다.
    """
    # 관리자 권한 체크
    AdminPermission.must_be_admin(current_user)
    return current_user


async def get_user_from_refresh_token(refresh_token: str) -> User:
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        uid = int(user_id)

    except (jwt.PyJWTError, ValidationError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
        ) from err

    user = await User.get_or_none(id=uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


async def get_current_user_from_refresh_cookie(
    refresh_token: str | None = Cookie(None, alias="refresh_token"),
) -> User:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token 존재하지 않음",
        )

    return await get_user_from_refresh_token(refresh_token)


logger = logging.getLogger("uvicorn.error")


async def get_current_user_from_refresh_cookie_ws(ws: WebSocket) -> User:
    refresh_token = ws.cookies.get("refresh_token")

    if not refresh_token:
        raise WebSocketException(code=1008)

    try:
        return await get_user_from_refresh_token(refresh_token)
    except HTTPException as e:
        if e.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND):
            raise WebSocketException(code=1008) from e
        raise
