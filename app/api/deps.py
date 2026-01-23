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
from app.domains.users.models import User

security = HTTPBearer()


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


async def _get_user_from_refresh_token(refresh_token: str) -> User:
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

    return await _get_user_from_refresh_token(refresh_token)


logger = logging.getLogger("uvicorn.error")


async def get_current_user_from_refresh_cookie_ws(ws: WebSocket) -> User:
    refresh_token = ws.cookies.get("refresh_token")

    if not refresh_token:
        raise WebSocketException(code=1008)

    try:
        return await _get_user_from_refresh_token(refresh_token)
    except HTTPException as e:
        if e.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND):
            raise WebSocketException(code=1008) from e
        raise
