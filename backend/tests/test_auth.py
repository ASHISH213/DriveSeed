"""Unit and integration tests for Google OAuth authentication and session handling."""

import urllib.parse
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_auth_service
from app.core.db import get_db_session
from app.core.security import (
    create_session_token,
    decrypt_token,
    encrypt_token,
    verify_session_token,
)
from app.main import create_app
from app.services.auth import AuthService
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_google_auth import FakeGoogleOAuthClient


def test_token_encryption_and_decryption() -> None:
    """Verify refresh token encryption at rest using Fernet."""
    plain_token = "1//04example_google_refresh_token_xyz"
    encrypted = encrypt_token(plain_token)

    assert encrypted != plain_token
    assert len(encrypted) > len(plain_token)

    decrypted = decrypt_token(encrypted)
    assert decrypted == plain_token


def test_session_token_creation_and_validation() -> None:
    """Verify session cookie token generation and expiration validation."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_session_token(user_id=user_id, max_age_seconds=3600)

    # Valid token
    assert verify_session_token(token) == user_id

    # Tampered token
    assert verify_session_token(token + "corrupt") is None

    # Expired token
    expired_token = create_session_token(user_id=user_id, max_age_seconds=-1)
    assert verify_session_token(expired_token) is None


@pytest.mark.asyncio
async def test_auth_login_endpoints() -> None:
    """Verify GET /api/auth/login provides OAuth URL with drive.file scope."""
    fake_google = FakeGoogleOAuthClient()
    auth_service = AuthService(oauth_client=fake_google)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. JSON mode
        resp_json = await client.get("/api/auth/login?redirect_browser=false")
        assert resp_json.status_code == 200
        url = resp_json.json()["url"]
        assert "accounts.google.com" in url
        assert "drive.file" in url
        # Hard rule: MUST NOT request full drive scope
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        scopes = params["scope"][0].split()
        assert "https://www.googleapis.com/auth/drive.file" in scopes
        assert "https://www.googleapis.com/auth/drive" not in scopes

        # 2. Redirect mode
        resp_redir = await client.get(
            "/api/auth/login?redirect_browser=true", follow_redirects=False
        )
        assert resp_redir.status_code == 307
        assert "accounts.google.com" in resp_redir.headers["location"]


@pytest.mark.asyncio
async def test_auth_callback_flow_encrypts_token_and_sets_cookie() -> None:
    """Verify OAuth callback saves user, encrypts refresh token, and sets session cookie."""
    fake_db = FakeAsyncSession()
    fake_google = FakeGoogleOAuthClient()
    fake_google.add_mock_code(
        code="auth-code-123",
        sub="google-sub-999",
        email="user@driveseed.io",
        refresh_token="google-refresh-token-999",
    )
    auth_service = AuthService(oauth_client=fake_google)

    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db

    # Generate valid state
    state = auth_service.get_login_url().split("state=")[1].split("&")[0]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/auth/callback?code=auth-code-123&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == "/"
        assert "driveseed_session" in resp.cookies

        # Verify user persisted in database
        assert len(fake_db.users) == 1
        user = list(fake_db.users.values())[0]
        assert user.email == "user@driveseed.io"
        assert user.google_sub == "google-sub-999"

        # Verify refresh token is encrypted at rest and not plain text
        assert user.drive_refresh_token_enc is not None
        assert user.drive_refresh_token_enc != "google-refresh-token-999"
        assert decrypt_token(user.drive_refresh_token_enc) == "google-refresh-token-999"


@pytest.mark.asyncio
async def test_auth_callback_invalid_state_rejected() -> None:
    """Verify callback fails when state parameter is invalid or tampered."""
    fake_db = FakeAsyncSession()
    fake_google = FakeGoogleOAuthClient()
    auth_service = AuthService(oauth_client=fake_google)

    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/auth/callback?code=some-code&state=bad-state",
            follow_redirects=False,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "invalid_state"


@pytest.mark.asyncio
async def test_auth_me_and_logout_endpoints() -> None:
    """Verify GET /api/auth/me returns user info with session, and logout clears cookie."""
    fake_db = FakeAsyncSession()
    fake_google = FakeGoogleOAuthClient()
    fake_google.add_mock_code(
        code="code-me",
        sub="google-sub-me",
        email="me@example.com",
    )
    auth_service = AuthService(oauth_client=fake_google)

    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request to /me -> 401
        unauth_resp = await client.get("/api/auth/me")
        assert unauth_resp.status_code == 401
        assert unauth_resp.json()["detail"]["error"]["code"] == "unauthorized"

        # 2. Complete login flow to obtain session
        state = auth_service.get_login_url().split("state=")[1].split("&")[0]
        cb_resp = await client.get(
            f"/api/auth/callback?code=code-me&state={state}",
            follow_redirects=False,
        )
        session_token = cb_resp.cookies.get("driveseed_session")
        assert session_token is not None

        # 3. Authenticated request to /me
        client.cookies.set("driveseed_session", session_token)
        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 200
        user_data = me_resp.json()
        assert user_data["email"] == "me@example.com"
        assert "id" in user_data

        # 4. Logout endpoint clears cookie
        logout_resp = await client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_auth_rate_limit_exceeded() -> None:
    """Verify exceeding RATE_LIMIT_AUTH_PER_MINUTE on /api/auth/login returns 429."""
    from app.core.rate_limit import get_auth_rate_limiter

    limiter = get_auth_rate_limiter()
    limiter.reset()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 20 requests (default RATE_LIMIT_AUTH_PER_MINUTE is 20)
        for _ in range(20):
            res = await client.get("/api/auth/login?redirect_browser=false")
            assert res.status_code == 200

        # 21st request triggers rate limit 429
        res21 = await client.get("/api/auth/login?redirect_browser=false")
        assert res21.status_code == 429
        body = res21.json()
        assert body["detail"]["error"]["code"] == "rate_limit_exceeded"
        assert "Retry-After" in res21.headers

    limiter.reset()
