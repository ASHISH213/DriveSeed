"""Service managing webhook endpoint registration, HMAC signatures, and event delivery."""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ssrf import SSRFError, validate_url
from app.models.task import Task
from app.models.webhook import WebhookEndpoint

logger = logging.getLogger(__name__)


class WebhookService:
    """Manages lifecycle of webhook endpoints and signed event dispatching."""

    @staticmethod
    def compute_signature(secret: str, payload_bytes: bytes) -> str:
        """Compute HMAC-SHA256 hex digest for signed webhook delivery."""
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    async def create_endpoint(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        url: str,
        secret: str | None = None,
        events: list[str] | None = None,
        allow_local: bool = False,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint for a user."""
        try:
            await validate_url(url, allow_local=allow_local)
        except SSRFError as err:
            raise ValueError(f"Invalid webhook URL: {err}") from err

        final_secret = (
            secret.strip() if secret and secret.strip() else f"whsec_{secrets.token_urlsafe(24)}"
        )
        event_list = [e.strip() for e in events] if events else ["task.completed", "task.failed"]
        events_str = ",".join(event_list)

        endpoint = WebhookEndpoint(
            id=uuid.uuid4(),
            user_id=user_id,
            url=url.strip(),
            secret=final_secret,
            events=events_str,
            is_active=True,
            created_at=datetime.now(UTC),
        )

        db.add(endpoint)
        await db.commit()
        await db.refresh(endpoint)
        return endpoint

    async def list_endpoints(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Sequence[WebhookEndpoint]:
        """List all registered webhook endpoints for a user."""
        stmt = (
            select(WebhookEndpoint)
            .where(WebhookEndpoint.user_id == user_id)
            .order_by(WebhookEndpoint.created_at.desc())
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def delete_endpoint(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        endpoint_id: uuid.UUID,
    ) -> bool:
        """Delete a registered webhook endpoint."""
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.user_id == user_id,
        )
        res = await db.execute(stmt)
        endpoint = res.scalar_one_or_none()

        if endpoint is None:
            return False

        await db.delete(endpoint)
        await db.commit()
        return True

    async def deliver_payload(
        self,
        url: str,
        secret: str,
        event_name: str,
        payload_data: dict[str, Any],
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[bool, int | None, str]:
        """Deliver a signed JSON payload with retries on transient errors."""
        payload = {
            "event": event_name,
            "timestamp": datetime.now(UTC).isoformat(),
            **payload_data,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig = self.compute_signature(secret, body)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DriveSeed-Webhook/1.0",
            "X-DriveSeed-Signature": f"sha256={sig}",
            "X-DriveSeed-Event": event_name,
        }

        should_close_client = False
        http_client = client
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=10.0)
            should_close_client = True

        try:
            for attempt in range(max_retries):
                try:
                    resp = await http_client.post(url, content=body, headers=headers)
                    if resp.status_code < 500:
                        return (
                            resp.is_success,
                            resp.status_code,
                            resp.text[:200] if resp.text else f"HTTP {resp.status_code}",
                        )
                    # HTTP 5xx: retryable server error
                    logger.warning(
                        "Webhook delivery to %s failed with %s (attempt %d/%d)",
                        url,
                        resp.status_code,
                        attempt + 1,
                        max_retries,
                    )
                except (httpx.RequestError, httpx.TimeoutException) as exc:
                    logger.warning(
                        "Webhook request error to %s: %s (attempt %d/%d)",
                        url,
                        exc,
                        attempt + 1,
                        max_retries,
                    )
                    if attempt == max_retries - 1:
                        return False, None, str(exc)

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))

            return False, 500, "Max retries exceeded"
        finally:
            if should_close_client and http_client:
                await http_client.aclose()

    async def send_test_ping(
        self,
        endpoint: WebhookEndpoint,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[bool, int | None, str]:
        """Send a test ping event to an endpoint."""
        return await self.deliver_payload(
            url=endpoint.url,
            secret=endpoint.secret,
            event_name="ping",
            payload_data={
                "message": "DriveSeed webhook test event",
                "endpoint_id": str(endpoint.id),
            },
            max_retries=1,
            client=client,
        )

    async def dispatch_task_event(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_name: str,
        task: Task,
        client: httpx.AsyncClient | None = None,
    ) -> int:
        """Find active endpoints subscribed to event_name and deliver the task payload."""
        endpoints = await self.list_endpoints(db, user_id)
        if not endpoints:
            return 0

        task_dict = {
            "id": str(task.id),
            "name": task.name,
            "type": getattr(task, "source_type", getattr(task, "type", None)),
            "state": task.state,
            "size_bytes": task.size_bytes,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

        dispatched = 0
        for ep in endpoints:
            if not ep.is_active:
                continue
            subscribed_events = [e.strip() for e in ep.events.split(",")]
            if event_name in subscribed_events or "*" in subscribed_events:
                # Deliver payload
                try:
                    await self.deliver_payload(
                        url=ep.url,
                        secret=ep.secret,
                        event_name=event_name,
                        payload_data={"task": task_dict},
                        client=client,
                    )
                    dispatched += 1
                except Exception as err:
                    logger.error(
                        "Failed to dispatch webhook event %s to %s: %s", event_name, ep.url, err
                    )

        return dispatched
