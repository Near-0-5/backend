from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token


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