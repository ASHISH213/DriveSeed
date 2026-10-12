"""Service managing personal API tokens and authentication verification."""

import hashlib
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken
from app.models.user import User

TOKEN_PREFIX = "ds_"


class ApiTokenService:
    """Manages creation, verification, and revocation of personal API access tokens."""

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Compute SHA-256 hex digest for token verification at rest."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    async def create_token(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        label: str,
    ) -> tuple[ApiToken, str]:
        """Generate a cryptographically secure personal token and persist its hash."""
        raw_secret = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        token_hash = self.hash_token(raw_secret)
        prefix = raw_secret[:10]

        token_record = ApiToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            prefix=prefix,
            label=label.strip(),
            created_at=datetime.now(UTC),
            last_used_at=None,
        )

        db.add(token_record)
        await db.commit()
        await db.refresh(token_record)

        return token_record, raw_secret

    async def verify_token(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> User | None:
        """Verify token hash and return associated User if valid, updating last_used_at."""
        if not raw_token or not raw_token.startswith(TOKEN_PREFIX):
            return None

        token_hash = self.hash_token(raw_token)
        stmt = select(ApiToken).where(ApiToken.token_hash == token_hash)
        res = await db.execute(stmt)
        token_record = res.scalar_one_or_none()

        if token_record is None:
            return None

        user = await db.get(User, token_record.user_id)
        if user is None:
            return None

        token_record.last_used_at = datetime.now(UTC)
        await db.commit()

        return user

    async def list_tokens(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Sequence[ApiToken]:
        """List active tokens for a specific user ordered by newest first."""
        stmt = (
            select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.created_at.desc())
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def revoke_token(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        token_id: uuid.UUID,
    ) -> bool:
        """Revoke (delete) a specific user token."""
        stmt = select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
        res = await db.execute(stmt)
        token_record = res.scalar_one_or_none()

        if token_record is None:
            return False

        await db.delete(token_record)
        await db.commit()
        return True
