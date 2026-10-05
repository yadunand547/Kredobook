"""
Loan Management System - Database Configuration

Connects to Neon PostgreSQL using DATABASE_URL from environment variables.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _get_database_url() -> str:
    """
    Ensure the DATABASE_URL uses the psycopg2 driver.
    Neon provides URLs with 'postgresql://' which SQLAlchemy 2.x maps to
    psycopg (v3) by default. We explicitly use postgresql+psycopg2://.
    """
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# Use the pooled connection URL for SQLAlchemy
engine = create_engine(
    _get_database_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """
    Dependency that provides a database session.
    Yields a session and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
