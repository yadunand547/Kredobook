"""
Integration tests for Module 3: Loan Management.
"""

import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.utils.security import hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    """Create/get admin and return JWT."""
    email = "loan_test_admin@example.com"
    password = "AdminTestPass!"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name="Loan Test Admin",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
        else:
            user.password_hash = hash_password(password)
            user.is_active = True
            db.commit()
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def borrower_data():
    """Create a borrower and return (token, user_id)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"loan_borrower_{suffix}@example.com"
    password = "BorrowerPass!"
    db = SessionLocal()
    try:
        user = User(
            name=f"Loan Borrower {suffix}",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.BORROWER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"token": r.json()["access_token"], "id": uid, "email": email}


@pytest.fixture(scope="module")
def second_borrower_data():
    """Create a second borrower for cross-access tests."""
    suffix = uuid.uuid4().hex[:6]
    email = f"loan_borrower2_{suffix}@example.com"
    password = "Borrower2Pass!"
    db = SessionLocal()
    try:
        user = User(
            name=f"Loan Borrower 2 {suffix}",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.BORROWER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"token": r.json()["access_token"], "id": uid}


# ── Admin Loan CRUD Tests ───────────────────────────────────────────

def test_admin_create_loan(admin_token, borrower_data):
    """Admin can create a loan for a borrower."""
    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 5000,
            "loan_date": "2026-09-24",
            "total_payable": 6000,
            "minimum_monthly_payment": 500,
            "notes": "Personal loan test",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["borrower_id"] == borrower_data["id"]
    assert Decimal(str(data["loan_amount"])) == Decimal("5000")
    assert Decimal(str(data["total_payable"])) == Decimal("6000")
    assert Decimal(str(data["total_paid"])) == Decimal("0")
    assert Decimal(str(data["remaining_balance"])) == Decimal("6000")
    assert data["status"] == "ACTIVE"
    assert data["borrower"]["id"] == borrower_data["id"]


def test_admin_create_second_loan_same_borrower(admin_token, borrower_data):
    """Multiple loans can exist for the same borrower."""
    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 2000,
            "loan_date": "2026-10-01",
            "total_payable": 2400,
            "minimum_monthly_payment": 200,
        },
    )
    assert r.status_code == 201
    assert r.json()["borrower_id"] == borrower_data["id"]


def test_admin_cannot_assign_loan_to_admin(admin_token):
    """Loans can only be assigned to BORROWER role users."""
    # Get admin user id
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"}).json()
    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": me["id"],
            "loan_amount": 1000,
            "loan_date": "2026-10-01",
            "total_payable": 1200,
            "minimum_monthly_payment": 100,
        },
    )
    assert r.status_code == 400
    assert "BORROWER" in r.json()["detail"]


def test_admin_cannot_assign_loan_to_inactive_borrower(admin_token):
    """Cannot create a loan for a deactivated borrower."""
    suffix = uuid.uuid4().hex[:6]
    email = f"inactive_{suffix}@example.com"
    db = SessionLocal()
    try:
        user = User(
            name="Inactive Borrower",
            email=email,
            password_hash=hash_password("pass"),
            role=UserRole.BORROWER,
            is_active=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
    finally:
        db.close()

    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": uid,
            "loan_amount": 1000,
            "loan_date": "2026-10-01",
            "total_payable": 1200,
            "minimum_monthly_payment": 100,
        },
    )
    assert r.status_code == 400
    assert "deactivated" in r.json()["detail"].lower()


def test_invalid_financial_values_rejected(admin_token, borrower_data):
    """Negative or zero financial values are rejected."""
    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": -100,
            "loan_date": "2026-10-01",
            "total_payable": 0,
            "minimum_monthly_payment": 0,
        },
    )
    assert r.status_code == 422


def test_admin_list_loans(admin_token):
    """Admin can list all loans."""
    r = client.get("/loans", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    loans = r.json()
    assert isinstance(loans, list)
    assert len(loans) >= 2  # we created at least 2


def test_admin_get_loan(admin_token, borrower_data):
    """Admin can view a single loan with computed balances."""
    # Get loan list and pick one
    loans = client.get("/loans", headers={"Authorization": f"Bearer {admin_token}"}).json()
    loan_id = loans[0]["id"]

    r = client.get(f"/loans/{loan_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    data = r.json()
    assert "total_paid" in data
    assert "remaining_balance" in data
    assert "borrower" in data


def test_admin_update_loan(admin_token):
    """Admin can update loan fields."""
    loans = client.get("/loans", headers={"Authorization": f"Bearer {admin_token}"}).json()
    loan_id = loans[0]["id"]

    r = client.put(
        f"/loans/{loan_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Updated notes from test"},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Updated notes from test"


def test_admin_cannot_reduce_total_payable_below_paid(admin_token, borrower_data):
    """
    If verified payments exist, total_payable cannot drop below total_paid.
    We insert a VERIFIED payment directly for this test.
    """
    # Create a fresh loan
    cr = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 10000,
            "loan_date": "2026-10-01",
            "total_payable": 12000,
            "minimum_monthly_payment": 1000,
        },
    )
    loan_id = cr.json()["id"]

    # Insert a VERIFIED payment directly
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        payment = Payment(
            loan_id=loan_id,
            borrower_id=borrower_data["id"],
            amount=Decimal("5000"),
            payment_month="2026-10",
            payment_date=datetime.now(timezone.utc),
            status=PaymentStatus.VERIFIED,
        )
        db.add(payment)
        db.commit()
    finally:
        db.close()

    # Try to set total_payable below 5000
    r = client.put(
        f"/loans/{loan_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"total_payable": 3000},
    )
    assert r.status_code == 400
    assert "verified" in r.json()["detail"].lower() or "below" in r.json()["detail"].lower()


# ── Balance Calculation Tests ────────────────────────────────────────

def test_balance_with_verified_payments(admin_token, borrower_data):
    """Verified payments reduce remaining balance."""
    # Create loan
    cr = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 5000,
            "loan_date": "2026-09-24",
            "total_payable": 6000,
            "minimum_monthly_payment": 500,
        },
    )
    loan_id = cr.json()["id"]

    # Add VERIFIED payments
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        for amt in [500, 700, 1000]:
            p = Payment(
                loan_id=loan_id,
                borrower_id=borrower_data["id"],
                amount=Decimal(str(amt)),
                payment_month="2026-10",
                payment_date=datetime.now(timezone.utc),
                status=PaymentStatus.VERIFIED,
            )
            db.add(p)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/loans/{loan_id}", headers={"Authorization": f"Bearer {admin_token}"})
    data = r.json()
    assert Decimal(str(data["total_paid"])) == Decimal("2200")
    assert Decimal(str(data["remaining_balance"])) == Decimal("3800")


def test_pending_and_rejected_do_not_affect_balance(admin_token, borrower_data):
    """PENDING and REJECTED payments must NOT reduce balance."""
    # Create loan
    cr = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 1000,
            "loan_date": "2026-10-01",
            "total_payable": 1200,
            "minimum_monthly_payment": 100,
        },
    )
    loan_id = cr.json()["id"]

    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        # PENDING payment
        p1 = Payment(
            loan_id=loan_id,
            borrower_id=borrower_data["id"],
            amount=Decimal("500"),
            payment_month="2026-10",
            payment_date=datetime.now(timezone.utc),
            status=PaymentStatus.PENDING,
        )
        # REJECTED payment
        p2 = Payment(
            loan_id=loan_id,
            borrower_id=borrower_data["id"],
            amount=Decimal("300"),
            payment_month="2026-10",
            payment_date=datetime.now(timezone.utc),
            status=PaymentStatus.REJECTED,
        )
        db.add_all([p1, p2])
        db.commit()
    finally:
        db.close()

    r = client.get(f"/loans/{loan_id}", headers={"Authorization": f"Bearer {admin_token}"})
    data = r.json()
    # No verified payments, so total_paid = 0 and remaining = total_payable
    assert Decimal(str(data["total_paid"])) == Decimal("0")
    assert Decimal(str(data["remaining_balance"])) == Decimal("1200")


def test_no_payments_balance(admin_token, borrower_data):
    """Loan with no payments: total_paid=0, remaining=total_payable."""
    cr = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 3000,
            "loan_date": "2026-10-01",
            "total_payable": 3600,
            "minimum_monthly_payment": 300,
        },
    )
    data = cr.json()
    assert Decimal(str(data["total_paid"])) == Decimal("0")
    assert Decimal(str(data["remaining_balance"])) == Decimal("3600")


# ── Borrower Access Tests ────────────────────────────────────────────

def test_borrower_can_see_own_loans(borrower_data):
    """Borrower can list their own loans via /my/loans."""
    r = client.get(
        "/my/loans",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
    )
    assert r.status_code == 200
    loans = r.json()
    assert isinstance(loans, list)
    assert len(loans) >= 1
    # All loans should belong to this borrower (no borrower_id exposed in response but verify via detail)


def test_borrower_can_see_own_loan_detail(borrower_data):
    """Borrower can access detail for their own loan."""
    loans = client.get(
        "/my/loans",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
    ).json()
    loan_id = loans[0]["id"]

    r = client.get(
        f"/my/loans/{loan_id}",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "total_paid" in data
    assert "remaining_balance" in data


def test_borrower_cannot_see_other_borrowers_loan(borrower_data, second_borrower_data, admin_token):
    """Borrower cannot access a loan that belongs to another borrower."""
    # Create a loan for second borrower
    cr = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": second_borrower_data["id"],
            "loan_amount": 1000,
            "loan_date": "2026-10-01",
            "total_payable": 1200,
            "minimum_monthly_payment": 100,
        },
    )
    other_loan_id = cr.json()["id"]

    # First borrower tries to access it
    r = client.get(
        f"/my/loans/{other_loan_id}",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
    )
    assert r.status_code == 404


def test_borrower_cannot_create_loan(borrower_data):
    """Borrower cannot create a loan (admin-only)."""
    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
        json={
            "borrower_id": borrower_data["id"],
            "loan_amount": 1000,
            "loan_date": "2026-10-01",
            "total_payable": 1200,
            "minimum_monthly_payment": 100,
        },
    )
    assert r.status_code == 403


def test_borrower_cannot_update_loan(borrower_data):
    """Borrower cannot update a loan (admin-only)."""
    loans = client.get(
        "/my/loans",
        headers={"Authorization": f"Bearer {borrower_data['token']}"},
    ).json()
    if loans:
        loan_id = loans[0]["id"]
        r = client.put(
            f"/loans/{loan_id}",
            headers={"Authorization": f"Bearer {borrower_data['token']}"},
            json={"notes": "hacked"},
        )
        assert r.status_code == 403


def test_unauthenticated_cannot_access_loans():
    """Unauthenticated users cannot access loan endpoints."""
    assert client.get("/loans").status_code in (401, 403)
    assert client.get("/my/loans").status_code in (401, 403)


# ── Dashboard Stats Tests ────────────────────────────────────────────

def test_admin_dashboard_stats(admin_token):
    """Admin dashboard stats endpoint returns correct fields."""
    r = client.get("/loans/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    data = r.json()
    assert "total_borrowers" in data
    assert "active_loans" in data
    assert "total_amount_lent" in data
    assert "total_outstanding" in data
    assert data["total_borrowers"] >= 1
    assert data["active_loans"] >= 1


def test_borrower_dashboard_stats(borrower_data):
    """Borrower dashboard stats endpoint returns correct fields."""
    r = client.get("/my/stats", headers={"Authorization": f"Bearer {borrower_data['token']}"})
    assert r.status_code == 200
    data = r.json()
    assert "active_loans" in data
    assert "total_outstanding" in data
    assert data["active_loans"] >= 1
