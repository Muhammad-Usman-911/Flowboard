from fastapi import APIRouter, Request, status

from app.api.deps import RedisDep, SessionDep
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserMe
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserMe,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Email or username taken"}},
)
async def register(data: UserCreate, session: SessionDep) -> UserMe:
    """Create an account. Passwords need 8+ characters with a letter and a digit."""
    user = await AuthService(session).register(data)
    return UserMe.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    responses={
        401: {"model": ErrorResponse, "description": "Wrong email or password"},
        429: {"model": ErrorResponse, "description": "Too many attempts"},
    },
)
async def login(
    data: LoginRequest, request: Request, session: SessionDep, redis: RedisDep
) -> TokenPair:
    """Exchange email + password for an access token and a refresh token.
    Limited to 5 attempts per minute per IP and email."""
    client_ip = request.client.host if request.client else "unknown"
    return await AuthService(session, redis).login(data.email, data.password, client_ip)


@router.post(
    "/refresh",
    response_model=TokenPair,
    responses={401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"}},
)
async def refresh(data: RefreshRequest, session: SessionDep) -> TokenPair:
    """Get a fresh token pair using a refresh token (the frontend does this automatically
    when an access token expires)."""
    return await AuthService(session).refresh(data.refresh_token)
