"""
Loan Management System - Application Configuration

Loads settings from environment variables / .env files.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is the parent of the 'backend' directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str
    JWT_SECRET: str = "change-me-in-production-super-secret-jwt-key-minimum-32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # Email Reminder Configuration (KredoBook)
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = "kredobook@gmail.com"
    EMAIL_PASSWORD: str = "teyu vgtl jjwx jkyg"
    EMAIL_FROM: str = "kredobook@gmail.com"
    EMAIL_FROM_NAME: str = "KredoBook"
    EMAIL_ENABLED: bool = True

    # Uploads
    UPLOAD_MAX_SIZE: int = 5 * 1024 * 1024  # 5 MB


    model_config = SettingsConfigDict(
        env_file=(
            str(PROJECT_ROOT / ".env.local"),
            str(PROJECT_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
