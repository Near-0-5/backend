from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, verify_cognito_token


def test_create_access_token():
    subject = "123"
    token = create_access_token(subject)

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == subject
    assert "exp" in payload


def test_create_access_token_with_expiry():
    subject = "test_user"
    expires_delta = timedelta(minutes=10)
    token = create_access_token(subject, expires_delta=expires_delta)

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == subject


@pytest.mark.asyncio
async def test_verify_cognito_token_success(mocker):
    # JWKS 응답 모킹
    mock_jwks = {
        "keys": [{"kid": "test_kid", "alg": "RS256", "kty": "RSA", "n": "...", "e": "..."}]
    }
    mocker.patch(
        "httpx.AsyncClient.get", return_value=mocker.Mock(status_code=200, json=lambda: mock_jwks)
    )

    # 전역 캐시 초기화
    mocker.patch("app.core.security._jwks_cache", None)

    # JWT 헤더 및 디코딩 모킹
    mocker.patch("jwt.get_unverified_header", return_value={"kid": "test_kid"})
    mocker.patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value="public_key")
    mocker.patch("jwt.decode", return_value={"sub": "user123", "email": "test@test.com"})

    payload = await verify_cognito_token("fake.token.segments")
    assert payload["sub"] == "user123"


@pytest.mark.asyncio
async def test_verify_cognito_token_errors(mocker):
    # Missing 36 (kid not found) & 52 (General Exception) 커버
    mock_jwks = {"keys": [{"kid": "other_kid"}]}
    mocker.patch("app.core.security._jwks_cache", mock_jwks)
    mocker.patch("jwt.get_unverified_header", return_value={"kid": "test_kid"})

    # kid 못 찾음 (Line 36)
    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("token")
    assert "kid not found" in exc.value.detail

    # 일반 예외 (Line 52)
    mocker.patch("jwt.decode", side_effect=Exception("Unknown Error"))
    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("token")
    assert "Token validation failed" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_cognito_token_invalid_kid(mocker):
    # JWKS에 존재하지 않는 kid 시나리오
    mock_jwks = {"keys": [{"kid": "existing_kid"}]}
    mocker.patch(
        "httpx.AsyncClient.get", return_value=mocker.Mock(status_code=200, json=lambda: mock_jwks)
    )
    mocker.patch("jwt.get_unverified_header", return_value={"kid": "wrong_kid"})

    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("fake_token")
    assert exc.value.status_code == 401
    assert "kid not found" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_cognito_token_expired(mocker):
    # Expired 에러가 직접적으로 발생하도록 side_effect 설정
    mocker.patch("jwt.get_unverified_header", return_value={"kid": "some_kid"})
    # 캐시가 이미 있다고 가정하거나 모킹
    mocker.patch("app.core.security._jwks_cache", {"keys": [{"kid": "some_kid"}]})
    mocker.patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value="pub_key")
    mocker.patch("jwt.decode", side_effect=jwt.ExpiredSignatureError())

    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("fake_token")
    assert exc.value.detail == "Token has expired"
