"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for DriveSeed backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime profile: "server" (default) or "colab"
    PROFILE: Literal["server", "colab"] = "server"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-in-production-to-a-secure-random-secret"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    # Database & Redis
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/driveseed"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage & Temp directory
    TEMP_DOWNLOAD_DIR: str = "./temp"

    # Security & Encryption (Fernet key for Google Drive refresh tokens)
    FERNET_KEY: str = ""

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: object) -> list[str]:
        """Parse comma-separated origins string into a list if needed."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin) for origin in value]
        return ["http://localhost:5173", "http://localhost:8000"]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
