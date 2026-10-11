"""Authentication API router for Google OAuth, sessions, and user info."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.security import create_session_token
from app.models.user import User
from app.schemas.auth import AuthUrlResponse, UserResponse
from app.services.auth import AuthError, AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(settings=settings)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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

    user = await auth_service.get_current_user(db, session_token)
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

    return await auth_service.get_current_user(db, session_token)


@router.get("/login", response_model=AuthUrlResponse)
async def login(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    redirect_to: str = Query(default="/", description="Post-login destination"),
    redirect_browser: bool = Query(
        default=True, description="Directly redirect browser or return JSON"
    ),
) -> Response:
    """Initiate Google OAuth login flow."""
    url = auth_service.get_login_url(redirect_to=redirect_to)
    if redirect_browser:
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return JSONResponse(content={"url": url})


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Handle Google OAuth redirect callback."""
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
