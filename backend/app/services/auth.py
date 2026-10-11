"""Authentication service and Google OAuth 2.0 integration."""

import urllib.parse
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import (
    create_oauth_state,
    encrypt_token,
    verify_oauth_state,
    verify_session_token,
)
from app.models.user import User

# Strictly requested scopes: drive.file ONLY (PRD section 10 and AGENTS.md hard rules)
GOOGLE_OAUTH_SCOPES: list[str] = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
]


class AuthError(Exception):
    """Domain exception for authentication and OAuth errors."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GoogleOAuthClient(Protocol):
    """Protocol for Google OAuth authorization code and token flows."""

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Construct Google OAuth 2.0 authorization URL."""
        ...

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange auth code for tokens and user profile."""
        ...


class RealGoogleOAuthClient:
    """Production Google OAuth client using Google OAuth 2.0 endpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": self.settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.settings.GOOGLE_CLIENT_ID,
            "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, data=data)
            if resp.status_code != 200:
                raise AuthError(
                    code="oauth_exchange_failed",
                    message="Failed to exchange authorization code with Google",
                )
            tokens = resp.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")

            # Fetch user profile using access token
            userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
            user_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                raise AuthError(
                    code="oauth_userinfo_failed",
                    message="Failed to fetch user profile from Google",
                )
            profile = user_resp.json()

            return {
                "sub": profile["sub"],
                "email": profile["email"],
                "refresh_token": refresh_token,
            }


class AuthService:
    """Service handling OAuth lifecycle, user registration, and sessions."""

    def __init__(
        self,
        oauth_client: GoogleOAuthClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.oauth_client = oauth_client or RealGoogleOAuthClient(self.settings)

    def get_login_url(self, redirect_to: str = "/") -> str:
        """Generate Google OAuth login URL with encrypted CSRF state parameter."""
        state = create_oauth_state(redirect_to=redirect_to)
        return self.oauth_client.get_authorization_url(
            state=state,
            redirect_uri=self.settings.GOOGLE_REDIRECT_URI,
        )

    async def handle_callback(
        self,
        db: AsyncSession,
        code: str,
        state: str,
    ) -> tuple[User, str]:
        """Process callback from Google, persisting user with encrypted refresh token."""
        state_data = verify_oauth_state(state)
        if not state_data:
            raise AuthError(
                code="invalid_state",
                message="OAuth state is missing, invalid, or expired",
            )

        redirect_to = str(state_data.get("redirect_to", "/"))

        # Exchange authorization code for tokens and identity
        profile = await self.oauth_client.exchange_code(
            code=code,
            redirect_uri=self.settings.GOOGLE_REDIRECT_URI,
        )

        google_sub = str(profile["sub"])
        email = str(profile["email"])
        refresh_token = profile.get("refresh_token")

        # Query existing user
        stmt = select(User).where((User.google_sub == google_sub) | (User.email == email))
        result = await db.execute(stmt)
        user = result.scalars().first()

        if user:
            # Update user info and refresh token if present
            user.google_sub = google_sub
            user.email = email
            if refresh_token:
                user.drive_refresh_token_enc = encrypt_token(refresh_token)
        else:
            # Create new user
            user = User(
                google_sub=google_sub,
                email=email,
                drive_refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
                created_at=datetime.now(UTC),
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

        return user, redirect_to

    async def get_current_user(
        self,
        db: AsyncSession,
        session_token: str | None,
    ) -> User | None:
        """Retrieve User corresponding to a decrypted session cookie."""
        if not session_token:
            return None

        user_id_str = verify_session_token(session_token)
        if not user_id_str:
            return None

        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            return None

        stmt = select(User).where(User.id == user_uuid)
        result = await db.execute(stmt)
        return result.scalars().first()
