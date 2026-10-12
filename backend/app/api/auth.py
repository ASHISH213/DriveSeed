"""Authentication API router for Google OAuth, sessions, and user info."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.rate_limit import SlidingWindowRateLimiter, get_auth_rate_limiter
from app.core.security import create_session_token
from app.models.user import User
from app.schemas.auth import AuthUrlResponse, UserResponse
from app.services.auth import AuthError, AuthService
from app.services.token import ApiTokenService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(settings=settings)


def get_token_service() -> ApiTokenService:
    """Dependency provider for ApiTokenService."""
    return ApiTokenService()


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token_service: Annotated[ApiTokenService, Depends(get_token_service)],
) -> User:
    """Dependency that resolves the authenticated User or raises 401."""
    settings = get_settings()
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:].strip()
    if not session_token:
        session_token = request.query_params.get("token")

    user: User | None = None
    if session_token:
        if session_token.startswith("ds_"):
            user = await token_service.verify_token(db, session_token)
        else:
            user = await auth_service.get_current_user(db, session_token)

    if not user and settings.PROFILE == "colab":
        from sqlalchemy import select

        colab_email = "colab@localhost"
        stmt = select(User).where(User.email == colab_email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            import uuid

            user = User(
                id=uuid.uuid4(),
                email=colab_email,
                google_sub="colab-local-owner",
                drive_root_folder_id="root",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "unauthorized",
                    "message": "Authentication required",
                }
            },
        )
    return user


async def get_optional_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token_service: Annotated[ApiTokenService, Depends(get_token_service)],
) -> User | None:
    """Dependency that resolves the authenticated User if logged in, else None."""
    settings = get_settings()
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:].strip()
    if not session_token:
        session_token = request.query_params.get("token")

    user: User | None = None
    if session_token:
        if session_token.startswith("ds_"):
            user = await token_service.verify_token(db, session_token)
        else:
            user = await auth_service.get_current_user(db, session_token)

    if not user and settings.PROFILE == "colab":
        from sqlalchemy import select

        colab_email = "colab@localhost"
        stmt = select(User).where(User.email == colab_email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            import uuid

            user = User(
                id=uuid.uuid4(),
                email=colab_email,
                google_sub="colab-local-owner",
                drive_root_folder_id="root",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

    return user


@router.get("/login", response_model=AuthUrlResponse)
async def login(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    auth_limiter: Annotated[SlidingWindowRateLimiter, Depends(get_auth_rate_limiter)],
    redirect_to: str = Query(default="/", description="Post-login destination"),
    redirect_browser: bool = Query(
        default=True, description="Directly redirect browser or return JSON"
    ),
) -> Response:
    """Initiate Google OAuth login flow."""
    client_ip = request.client.host if request.client else "unknown"
    await auth_limiter.check(client_ip)

    url = auth_service.get_login_url(redirect_to=redirect_to)
    if redirect_browser:
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return JSONResponse(content={"url": url})


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    auth_limiter: Annotated[SlidingWindowRateLimiter, Depends(get_auth_rate_limiter)],
) -> Response:
    """Handle Google OAuth redirect callback."""
    client_ip = request.client.host if request.client else "unknown"
    await auth_limiter.check(client_ip)

    try:
        user, redirect_to = await auth_service.handle_callback(
            db=db,
            code=code,
            state=state,
        )
    except AuthError as err:
        return JSONResponse(
            status_code=err.status_code,
            content={"error": {"code": err.code, "message": err.message}},
        )

    session_token = create_session_token(
        user_id=str(user.id),
        max_age_seconds=settings.SESSION_MAX_AGE_SECONDS,
    )

    response = RedirectResponse(url=redirect_to, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.SESSION_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Log out user by clearing the session cookie."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return currently authenticated user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )
