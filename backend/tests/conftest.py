"""
Global pytest configuration and automatic test data cleanup fixture.
Ensures that after running test suites, all test-generated records are purged.
"""

import pytest
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.loan import Loan
from app.models.payment import Payment
from app.models.reminder import ReminderLog
from app.utils.security import hash_password


@pytest.fixture(scope="session", autouse=True)
def clean_db_after_tests():
    """Runs before and after the entire test suite to guarantee a clean database."""
    # Yield to let tests execute
    yield

    # Teardown: purge test data
    db = SessionLocal()
    try:
        db.query(Payment).delete()
        db.query(Loan).delete()
        db.query(ReminderLog).delete()
        db.query(User).filter(User.role == UserRole.BORROWER).delete()
        db.query(User).filter(User.role == UserRole.ADMIN, User.email != "admin@loantracker.com").delete()

        # Keep main admin
        admin = db.query(User).filter(User.email == "admin@loantracker.com").first()
        if not admin:
            admin = User(
                name="System Admin",
                email="admin@loantracker.com",
                password_hash=hash_password("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
        else:
            admin.password_hash = hash_password("AdminPass123!")
            admin.role = UserRole.ADMIN
            admin.is_active = True

        db.commit()
    finally:
        db.close()
