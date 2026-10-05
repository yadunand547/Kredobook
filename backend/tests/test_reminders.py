"""
Integration tests for Module 6: Monthly Email Reminders and Settings.
"""

import uuid
from decimal import Decimal
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.models.reminder import ReminderLog
from app.services import reminder_service
from app.services.reminder_service import send_monthly_reminders_for_all
from app.utils.security import hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_reminder_email_delivery(monkeypatch):
    """Keep reminder behavior tests offline and independent of Brevo credentials."""
    monkeypatch.setattr(
        reminder_service,
        "send_monthly_reminder_email",
        lambda **kwargs: (True, None),
    )


@pytest.fixture(scope="module")
def admin_token():
    """Ensure an admin user exists and return a valid JWT token."""
    email = "rem_admin@example.com"
    password = "AdminPass123!"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name="Reminder Admin",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
        else:
            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            db.commit()
    finally:
        db.close()

    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def borrower_token_and_id():
    """Ensure a test borrower exists and return token and user ID."""
    email = f"rem_borrower_{uuid.uuid4().hex[:6]}@example.com"
    password = "BorrowerPass123!"
    db = SessionLocal()
    try:
        user = User(
            name="Reminder Borrower",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.BORROWER,
            is_active=True,
            monthly_reminder_enabled=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        b_id = user.id
    finally:
        db.close()

    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"], b_id


def test_reminder_dispatch_eligible_borrower():
    """Verify that an active borrower with active loans receives an email reminder."""
    db = SessionLocal()
    try:
        unique_email = f"eligible_{uuid.uuid4().hex[:6]}@example.com"
        borrower = User(
            name="Eligible Borrower",
            email=unique_email,
            role=UserRole.BORROWER,
            password_hash=hash_password("pass123"),
            is_active=True,
            monthly_reminder_enabled=True,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)

        loan = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("5000.00"),
            total_payable=Decimal("6000.00"),
            minimum_monthly_payment=Decimal("500.00"),
            loan_date=date(2026, 1, 1),
            status=LoanStatus.ACTIVE,
        )
        db.add(loan)
        db.commit()

        initial_payment_count = db.query(Payment).count()

        month_key = f"2026-11-{uuid.uuid4().hex[:4]}"[:7]
        results = send_monthly_reminders_for_all(db, target_month=month_key)
        assert results["sent"] >= 1
        assert results["target_month"] == month_key

        # Verify log entry in DB
        log = (
            db.query(ReminderLog)
            .filter(ReminderLog.borrower_id == borrower.id, ReminderLog.reminder_month == month_key)
            .first()
        )
        assert log is not None
        assert log.status == "SENT"
        assert log.loans_count == 1
        assert log.total_outstanding == Decimal("6000.00")

        # CRITICAL: Verify NO payment records were generated
        assert db.query(Payment).count() == initial_payment_count
        # Verify loan balance is unchanged
        db.refresh(loan)
        assert loan.loan_amount == Decimal("5000.00")
        assert loan.total_payable == Decimal("6000.00")
    finally:
        db.close()


def test_reminder_skipped_when_reminders_disabled():
    """Borrower with monthly_reminder_enabled=False must be skipped."""
    db = SessionLocal()
    try:
        unique_email = f"disabled_{uuid.uuid4().hex[:6]}@example.com"
        borrower = User(
            name="Disabled Reminder Borrower",
            email=unique_email,
            role=UserRole.BORROWER,
            password_hash=hash_password("pass123"),
            is_active=True,
            monthly_reminder_enabled=False,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)

        loan = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("3000.00"),
            total_payable=Decimal("3500.00"),
            minimum_monthly_payment=Decimal("350.00"),
            loan_date=date(2026, 1, 1),
            status=LoanStatus.ACTIVE,
        )
        db.add(loan)
        db.commit()

        month_key = "2026-12"
        results = send_monthly_reminders_for_all(db, target_month=month_key)
        # Verify not sent to this borrower
        log = (
            db.query(ReminderLog)
            .filter(ReminderLog.borrower_id == borrower.id, ReminderLog.reminder_month == month_key)
            .first()
        )
        assert log is None or log.status == "SKIPPED"
    finally:
        db.close()


def test_reminder_skipped_when_no_active_balance():
    """Borrower with only PAID or 0-balance loans must not receive reminders."""
    db = SessionLocal()
    try:
        unique_email = f"paid_{uuid.uuid4().hex[:6]}@example.com"
        borrower = User(
            name="Paid Off Borrower",
            email=unique_email,
            role=UserRole.BORROWER,
            password_hash=hash_password("pass123"),
            is_active=True,
            monthly_reminder_enabled=True,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)

        loan = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("1000.00"),
            total_payable=Decimal("1000.00"),
            minimum_monthly_payment=Decimal("100.00"),
            loan_date=date(2026, 1, 1),
            status=LoanStatus.PAID,
        )
        db.add(loan)
        db.commit()
        db.refresh(loan)

        # Full payment verified
        payment = Payment(
            loan_id=loan.id,
            borrower_id=borrower.id,
            amount=Decimal("1000.00"),
            payment_month="2026-01",
            payment_date=date(2026, 1, 10),
            status=PaymentStatus.VERIFIED,
        )
        db.add(payment)
        db.commit()

        month_key = "2027-03"
        results = send_monthly_reminders_for_all(db, target_month=month_key)
        log = (
            db.query(ReminderLog)
            .filter(ReminderLog.borrower_id == borrower.id, ReminderLog.reminder_month == month_key)
            .first()
        )
        assert log is None or log.status == "SKIPPED"
    finally:
        db.close()


def test_reminder_idempotency_duplicate_prevention():
    """Running reminders multiple times in the same month must not duplicate dispatch."""
    db = SessionLocal()
    try:
        unique_email = f"idem_{uuid.uuid4().hex[:6]}@example.com"
        borrower = User(
            name="Idempotency Borrower",
            email=unique_email,
            role=UserRole.BORROWER,
            password_hash=hash_password("pass123"),
            is_active=True,
            monthly_reminder_enabled=True,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)

        loan = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("4000.00"),
            total_payable=Decimal("4800.00"),
            minimum_monthly_payment=Decimal("400.00"),
            loan_date=date(2026, 1, 1),
            status=LoanStatus.ACTIVE,
        )
        db.add(loan)
        db.commit()

        month_key = f"2027-01-{uuid.uuid4().hex[:4]}"[:7]
        # First run: should send
        first_run = send_monthly_reminders_for_all(db, target_month=month_key)
        assert any(d["borrower_id"] == borrower.id and d["status"] == "SENT" for d in first_run["details"])

        # Second run for same month: must skip duplicate
        second_run = send_monthly_reminders_for_all(db, target_month=month_key)
        borrower_detail = next((d for d in second_run["details"] if d["borrower_id"] == borrower.id), None)
        assert borrower_detail is not None
        assert borrower_detail["status"] == "SKIPPED"
        assert "Already sent" in borrower_detail["reason"]
    finally:
        db.close()


def test_reminder_multi_loan_aggregation():
    """Borrower with multiple active loans receives a single aggregated reminder."""
    db = SessionLocal()
    try:
        unique_email = f"multi_{uuid.uuid4().hex[:6]}@example.com"
        borrower = User(
            name="Multi Loan Borrower",
            email=unique_email,
            role=UserRole.BORROWER,
            password_hash=hash_password("pass123"),
            is_active=True,
            monthly_reminder_enabled=True,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)

        # Loan 1: 5000 -> 6000 payable, 2200 paid -> 3800 remaining
        loan1 = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("5000.00"),
            total_payable=Decimal("6000.00"),
            minimum_monthly_payment=Decimal("500.00"),
            loan_date=date(2026, 1, 1),
            status=LoanStatus.ACTIVE,
        )
        # Loan 2: 2000 -> 2400 payable, 500 paid -> 1900 remaining
        loan2 = Loan(
            borrower_id=borrower.id,
            loan_amount=Decimal("2000.00"),
            total_payable=Decimal("2400.00"),
            minimum_monthly_payment=Decimal("400.00"),
            loan_date=date(2026, 2, 1),
            status=LoanStatus.ACTIVE,
        )
        db.add_all([loan1, loan2])
        db.commit()
        db.refresh(loan1)
        db.refresh(loan2)

        # Payments for loan 1
        p1 = Payment(
            loan_id=loan1.id,
            borrower_id=borrower.id,
            amount=Decimal("2200.00"),
            payment_month="2026-02",
            payment_date=date(2026, 2, 10),
            status=PaymentStatus.VERIFIED,
        )
        # Payments for loan 2
        p2 = Payment(
            loan_id=loan2.id,
            borrower_id=borrower.id,
            amount=Decimal("500.00"),
            payment_month="2026-02",
            payment_date=date(2026, 2, 15),
            status=PaymentStatus.VERIFIED,
        )
        db.add_all([p1, p2])
        db.commit()

        month_key = f"2027-02-{uuid.uuid4().hex[:4]}"[:7]
        results = send_monthly_reminders_for_all(db, target_month=month_key)
        log = (
            db.query(ReminderLog)
            .filter(ReminderLog.borrower_id == borrower.id, ReminderLog.reminder_month == month_key)
            .first()
        )
        assert log is not None
        assert log.status == "SENT"
        assert log.loans_count == 2
        # 3800 + 1900 = 5700 total outstanding
        assert log.total_outstanding == Decimal("5700.00")
    finally:
        db.close()


def test_admin_api_endpoints(admin_token, borrower_token_and_id):
    """Test RBAC and operation on reminder endpoints."""
    borrower_token, b_id = borrower_token_and_id

    # 1. Borrower cannot trigger monthly reminders (403)
    res = client.post(
        "/reminders/send-monthly",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    assert res.status_code == 403

    # 2. Admin CAN trigger monthly reminders (200)
    res = client.post(
        "/reminders/send-monthly",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "target_month" in data
    assert "sent" in data
    assert "skipped" in data

    # 3. Admin can view reminder logs
    res = client.get(
        "/reminders/logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)

    # 4. Admin can toggle borrower reminders
    res = client.patch(
        f"/borrowers/{b_id}/reminders",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["monthly_reminder_enabled"] is False

    # Toggle back
    res = client.patch(
        f"/borrowers/{b_id}/reminders",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["monthly_reminder_enabled"] is True
