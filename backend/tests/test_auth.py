from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


async def test_register_returns_public_profile(client: AsyncClient) -> None:
    r = await client.post(
        REGISTER,
        json={"email": "Sara@Example.com", "username": "Sara_Dev", "password": "Secret123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "sara@example.com"
    assert body["username"] == "sara_dev"
    assert "password" not in str(body) and "hashed" not in str(body)


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("short1", "at least 8"),
        ("onlyletters", "letter and one digit"),
        ("12345678", "letter and one digit"),
        ("a1" * 40, "72 bytes"),
    ],
)
async def test_password_rules(client: AsyncClient, password: str, message: str) -> None:
    r = await client.post(
        REGISTER, json={"email": "x@example.com", "username": "xuser", "password": password}
    )
    assert r.status_code == 422
    assert message in r.json()["detail"]


async def test_bad_username_rejected(client: AsyncClient) -> None:
    r = await client.post(
        REGISTER, json={"email": "x@example.com", "username": "no spaces!", "password": "Secret123"}
    )
    assert r.status_code == 422


async def test_duplicate_email_and_username(client: AsyncClient, make_user) -> None:
    await make_user("sara")
    r = await client.post(
        REGISTER, json={"email": "sara@example.com", "username": "other", "password": "Secret123"}
    )
    assert (r.status_code, r.json()["code"]) == (409, "email_taken")
    r = await client.post(
        REGISTER, json={"email": "new@example.com", "username": "SARA", "password": "Secret123"}
    )
    assert (r.status_code, r.json()["code"]) == (409, "username_taken")


async def test_login_and_me(client: AsyncClient, make_user) -> None:
    headers = await make_user("sara")
    r = await client.get("/api/v1/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "sara"


async def test_login_wrong_password(client: AsyncClient, make_user) -> None:
    await make_user("sara")
    r = await client.post(LOGIN, json={"email": "sara@example.com", "password": "Wrong1234"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"
    r = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "Wrong1234"})
    assert r.json()["code"] == "invalid_credentials"  # same answer: no user enumeration


async def test_login_is_rate_limited(client: AsyncClient, make_user) -> None:
    await make_user("sara")
    for _ in range(settings.login_rate_limit):
        r = await client.post(LOGIN, json={"email": "sara@example.com", "password": "Wrong1234"})
        assert r.status_code == 401
    r = await client.post(LOGIN, json={"email": "sara@example.com", "password": "Password123"})
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"


async def test_successful_login_resets_the_counter(client: AsyncClient, make_user) -> None:
    await make_user("sara")  # make_user already logged in once
    for _ in range(settings.login_rate_limit - 1):
        await client.post(LOGIN, json={"email": "sara@example.com", "password": "Wrong1234"})
    ok = await client.post(LOGIN, json={"email": "sara@example.com", "password": "Password123"})
    assert ok.status_code == 200
    again = await client.post(LOGIN, json={"email": "sara@example.com", "password": "Wrong1234"})
    assert again.status_code == 401  # not 429: the counter was reset


async def test_refresh_flow(client: AsyncClient, make_user) -> None:
    await make_user("sara")
    tokens = (
        await client.post(LOGIN, json={"email": "sara@example.com", "password": "Password123"})
    ).json()
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    new_access = r.json()["access_token"]
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200

    # An access token is not accepted where a refresh token is expected, and vice versa.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401
    r = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert r.status_code == 401


async def test_missing_invalid_and_expired_tokens(client: AsyncClient, make_user) -> None:
    r = await client.get("/api/v1/users/me")
    assert (r.status_code, r.json()["code"]) == (401, "not_authenticated")
    assert r.headers["www-authenticate"] == "Bearer"

    r = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.json()["code"] == "invalid_token"

    expired = jwt.encode(
        {"sub": "1", "type": "access", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.json()["code"] == "token_expired"


async def test_token_for_deleted_user(client: AsyncClient) -> None:
    from app.core.security import create_token

    token = create_token(999, "access")
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    r = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": create_token(999, "refresh")}
    )
    assert r.status_code == 401


async def test_update_profile_and_password(client: AsyncClient, make_user) -> None:
    headers = await make_user("sara")
    r = await client.patch(
        "/api/v1/users/me", json={"full_name": "Sara K", "password": "NewPass456"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Sara K"
    r = await client.post(LOGIN, json={"email": "sara@example.com", "password": "NewPass456"})
    assert r.status_code == 200
    r = await client.patch("/api/v1/users/me", json={"password": "weak"}, headers=headers)
    assert r.status_code == 422
