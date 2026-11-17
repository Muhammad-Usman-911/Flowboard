"""Registration, login, token refresh and profile updates."""

import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger("app.auth")


def issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_token(user_id, "access"),
        refresh_token=create_token(user_id, "refresh"),
        expires_in=settings.access_token_expire_minutes * 60,
    )


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None) -> None:
        self.session = session
        self.redis = redis
        self.users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.users.get_by_email(data.email):
            raise ConflictError("An account with this email already exists", "email_taken")
        if await self.users.get_by_username(data.username):
            raise ConflictError("This username is taken", "username_taken")
        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )
        await self.users.add(user)
        await self.session.commit()
        logger.info("User registered", extra={"fields": {"user_id": user.id}})
        return user

    async def login(self, email: str, password: str, client_ip: str) -> TokenPair:
        assert self.redis is not None
        key = f"rl:login:{client_ip}:{email.lower()}"
        # Count the attempt *before* checking the password, so guessing is rate limited.
        await rate_limit.hit(
            self.redis, key, settings.login_rate_limit, settings.login_rate_window_seconds
        )
        user = await self.users.get_by_email(email)
        # Same error for "no such user" and "wrong password": don't reveal which emails exist.
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password", "invalid_credentials")
        await rate_limit.reset(self.redis, key)
        return issue_tokens(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        user_id = decode_token(refresh_token, "refresh")
        if await self.users.get(user_id) is None:
            raise UnauthorizedError("User no longer exists", "invalid_token")
        return issue_tokens(user_id)

    async def update_profile(self, user: User, data: UserUpdate) -> User:
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.password is not None:
            user.hashed_password = hash_password(data.password)
        await self.session.commit()
        return user
