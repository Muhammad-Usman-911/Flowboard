"""Password hashing (bcrypt) and JSON Web Tokens (PyJWT).

Two kinds of JWT are issued at login:
- access token: short lived (15 min), sent on every request as `Authorization: Bearer ...`
- refresh token: long lived (7 days), only accepted by POST /auth/refresh to get a new pair

The `type` claim stops a refresh token from being used as an access token (and vice versa).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; our password rules cap the length at 72 too.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    if token_type == "access":
        expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expires = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),  # "subject": who the token is about (must be a string)
        "type": token_type,
        "iat": now,
        "exp": expires,
        "jti": uuid.uuid4().hex,  # unique id, handy if you later add token revocation
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> int:
    """Validate a token and return the user id inside it, or raise UnauthorizedError."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired", "token_expired") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid token", "invalid_token") from exc
    if payload.get("type") != expected_type:
        raise UnauthorizedError("Wrong token type", "invalid_token")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid token", "invalid_token") from exc
