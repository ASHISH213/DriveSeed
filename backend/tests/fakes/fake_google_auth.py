"""Fake Google OAuth client for automated testing without hitting Google servers."""

import urllib.parse
from typing import Any

from app.services.auth import AuthError


class FakeGoogleOAuthClient:
    """In-memory fake implementation of GoogleOAuthClient."""

    def __init__(self) -> None:
        self.code_store: dict[str, dict[str, Any]] = {}
        self.last_state: str | None = None

    def add_mock_code(
        self,
        code: str,
        sub: str = "google-sub-12345",
        email: str = "user@example.com",
        refresh_token: str | None = "mock-refresh-token-xyz",
    ) -> None:
        """Register a valid authorization code with its mock profile data."""
        self.code_store[code] = {
            "sub": sub,
            "email": email,
            "refresh_token": refresh_token,
        }

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        self.last_state = state
        params = {
            "client_id": "fake-client-id",
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if code not in self.code_store:
            raise AuthError(
                code="oauth_exchange_failed",
                message=f"Fake Google client rejected code '{code}'",
            )
        return self.code_store[code]
