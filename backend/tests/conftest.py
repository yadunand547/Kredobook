"""Pytest database isolation.

Tests must never connect to or delete data from the configured Neon production
database.  A shared in-memory SQLite database keeps FastAPI TestClient threads
and direct service tests on the same isolated database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base

# Import every model before creating tables so all mapped tables are registered
# in Base.metadata.
from app.models.loan import Loan  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.reminder import ReminderLog  # noqa: F401
from app.models.user import User  # noqa: F401


_test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Test modules import SessionLocal after this conftest module is loaded, and
# application dependencies resolve database.SessionLocal at request time.
database.engine = _test_engine
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Create and discard a local test database for the whole test session."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)
    _test_engine.dispose()
