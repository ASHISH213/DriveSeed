"""Health check schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = "ok"
    database: str | None = None
    redis: str | None = None
