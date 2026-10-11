"""Security utilities for token encryption, session cookies, and OAuth state."""

import base64
import hashlib
import json
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def get_fernet() -> Fernet:
    """Return a Fernet cipher instance using FERNET_KEY or derived from SECRET_KEY."""
    settings = get_settings()
    if settings.FERNET_KEY:
        try:
            return Fernet(settings.FERNET_KEY.encode("utf-8"))
        except Exception:
            pass

    # Deterministically derive 32-byte urlsafe-base64 key from SECRET_KEY
    derived = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(derived)
    return Fernet(key)


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plaintext token (e.g. Google refresh token) for at-rest storage."""
    fernet = get_fernet()
    return fernet.encrypt(plain_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token."""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")


def create_session_token(user_id: str, max_age_seconds: int = 14 * 24 * 3600) -> str:
    """Create an encrypted, timestamped session cookie token for a user."""
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + max_age_seconds,
    }
    raw_data = json.dumps(payload).encode("utf-8")
    return get_fernet().encrypt(raw_data).decode("utf-8")


def verify_session_token(token: str) -> str | None:
    """Verify and decrypt a session token, returning user_id or None if invalid/expired."""
    try:
        raw_bytes = base64.urlsafe_b64decode(token.encode("utf-8"))
        if base64.urlsafe_b64encode(raw_bytes).decode("utf-8") != token:
            return None
        decrypted = get_fernet().decrypt(token.encode("utf-8"))
        payload: dict[str, Any] = json.loads(decrypted.decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return str(payload.get("user_id"))
    except (InvalidToken, json.JSONDecodeError, KeyError, Exception):
        return None


def create_oauth_state(redirect_to: str = "/") -> str:
    """Create a tamper-proof encrypted OAuth state parameter with 10-minute expiry."""
    payload = {
        "redirect_to": redirect_to,
        "exp": int(time.time()) + 600,
    }
    raw = json.dumps(payload).encode("utf-8")
    return get_fernet().encrypt(raw).decode("utf-8")


def verify_oauth_state(state: str) -> dict[str, Any] | None:
    """Verify and extract OAuth state parameter, returning payload or None."""
    try:
        raw_bytes = base64.urlsafe_b64decode(state.encode("utf-8"))
        if base64.urlsafe_b64encode(raw_bytes).decode("utf-8") != state:
            return None
        decrypted = get_fernet().decrypt(state.encode("utf-8"))
        payload: dict[str, Any] = json.loads(decrypted.decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except (InvalidToken, json.JSONDecodeError, Exception):
        return None
