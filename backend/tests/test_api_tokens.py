"""Tests for Personal API Tokens, hashing at rest, and Bearer authentication."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.core.config import Settings
from app.core.db import get_db_session
from app.main import create_app
from app.models.user import User
from app.services.token import ApiTokenService
from tests.fakes.fake_db import FakeAsyncSession


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        google_sub="google-user-123",
        email="tokenuser@example.com",
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.mark.asyncio
async def test_api_token_service_hashing(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Ensure tokens are generated with ds_ prefix, SHA-256 hashed, and verifiable."""
    service = ApiTokenService()
    token_record, raw_secret = await service.create_token(
        db=fake_db,
        user_id=test_user.id,
        label="CI Pipeline",
    )

    assert raw_secret.startswith("ds_")
    assert token_record.label == "CI Pipeline"
    assert token_record.prefix == raw_secret[:10]
    assert token_record.token_hash == service.hash_token(raw_secret)
    assert token_record.token_hash != raw_secret
    assert len(token_record.token_hash) == 64
    assert token_record.last_used_at is None

    # Verification updates last_used_at
    verified_user = await service.verify_token(db=fake_db, raw_token=raw_secret)
    assert verified_user is not None
    assert verified_user.id == test_user.id
    assert token_record.last_used_at is not None

    # Invalid token fails
    assert await service.verify_token(db=fake_db, raw_token="ds_invalidtoken123") is None
    assert await service.verify_token(db=fake_db, raw_token="other_prefix_token") is None


@pytest.mark.asyncio
async def test_api_token_endpoints_crud(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test POST, GET, and DELETE /api/tokens endpoints."""
    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_db_session] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create token
        create_resp = await client.post(
            "/api/tokens",
            json={"label": "GitHub Actions"},
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert "token" in data
        raw_token = data["token"]
        assert raw_token.startswith("ds_")
        assert data["label"] == "GitHub Actions"
        assert data["prefix"] == raw_token[:10]
        token_id = data["id"]

        # List tokens
        list_resp = await client.get("/api/tokens")
        assert list_resp.status_code == 200
        tokens_list = list_resp.json()
        assert len(tokens_list) == 1
        assert tokens_list[0]["id"] == token_id
        assert tokens_list[0]["label"] == "GitHub Actions"
        assert "token" not in tokens_list[0]
        assert "token_hash" not in tokens_list[0]

        # Revoke token
        del_resp = await client.delete(f"/api/tokens/{token_id}")
        assert del_resp.status_code == 204

        # List again -> empty
        list_resp2 = await client.get("/api/tokens")
        assert list_resp2.status_code == 200
        assert len(list_resp2.json()) == 0

        # Revoke non-existent -> 404
        del_resp404 = await client.delete(f"/api/tokens/{token_id}")
        assert del_resp404.status_code == 404


@pytest.mark.asyncio
async def test_bearer_authentication_with_api_token(
    fake_db: FakeAsyncSession, test_user: User
) -> None:
    """Test authenticating against protected endpoints using Bearer ds_... token."""
    service = ApiTokenService()
    token_record, raw_secret = await service.create_token(
        db=fake_db,
        user_id=test_user.id,
        label="Desktop Client",
    )

    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_db_session] = lambda: fake_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Request with valid Bearer token
        headers = {"Authorization": f"Bearer {raw_secret}"}
        resp = await client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email

        # Token last_used_at was updated
        assert token_record.last_used_at is not None

        # Request with invalid token
        bad_headers = {"Authorization": "Bearer ds_nonexistenttoken"}
        bad_resp = await client.get("/api/auth/me", headers=bad_headers)
        assert bad_resp.status_code == 401

        # Request without headers
        unauth_resp = await client.get("/api/auth/me")
        assert unauth_resp.status_code == 401
