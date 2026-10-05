"""
Loan Management System - Application Configuration

Loads settings from environment variables / .env files.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is the parent of the 'backend' directory.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str
    JWT_SECRET: str = "change-me-in-production-super-secret-jwt-key-minimum-32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,https://kredobook.vercel.app"
    FRONTEND_URL: str = "https://kredobook.vercel.app"

    # Transactional email is delivered through Brevo's HTTPS API.  This works
    # on Render Free, where outbound SMTP ports are blocked.
    EMAIL_PROVIDER: str = "brevo"
    BREVO_API_KEY: str = ""
    EMAIL_FROM: str = "kredobook@gmail.com"
    EMAIL_FROM_NAME: str = "KredoBook"
    # Email must be deliberately enabled through an environment variable.
    EMAIL_ENABLED: bool = False

    # Uploads
    UPLOAD_MAX_SIZE: int = 5 * 1024 * 1024  # 5 MB


    model_config = SettingsConfigDict(
        # Support both documented locations. Root-level files take precedence,
        # while backend/.env keeps local FastAPI-only configuration convenient.
        env_file=(
            str(BACKEND_ROOT / ".env"),
            str(BACKEND_ROOT / ".env.local"),
            str(PROJECT_ROOT / ".env"),
            str(PROJECT_ROOT / ".env.local"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
