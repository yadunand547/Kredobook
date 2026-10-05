"""
Integration tests for Module 4: Payment Submission & Verification.
"""

import io
import uuid
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.utils.security import hash_password

client = TestClient(app)

# Minimal 1x1 valid PNG bytes for screenshot uploads
SAMPLE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00"
    b"\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def admin_user():
    """Create/get admin user and return (token, user_id)."""
    email = "payment_test_admin@example.com"
    password = "AdminTestPass123!"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name="Payment Test Admin",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.password_hash = hash_password(password)
            user.is_active = True
            db.commit()
            db.refresh(user)
        admin_id = user.id
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"], admin_id


@pytest.fixture(scope="module")
def borrower_one():
    """Create borrower 1 and return (token, user_id)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"pay_borrower_1_{suffix}@example.com"
    password = "BorrowerPass123!"
    db = SessionLocal()
    try:
        user = User(
            name=f"Pay Borrower One {suffix}",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.BORROWER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"], user_id


@pytest.fixture(scope="module")
def borrower_two():
    """Create borrower 2 and return (token, user_id)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"pay_borrower_2_{suffix}@example.com"
    password = "BorrowerPass123!"
    db = SessionLocal()
    try:
        user = User(
            name=f"Pay Borrower Two {suffix}",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.BORROWER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"], user_id


@pytest.fixture(scope="module")
def loan_for_b1(admin_user, borrower_one):
    """Create a loan for borrower 1 with loan_amount=10000, total_payable=12000, min_monthly=1000."""
    admin_token, _ = admin_user
    _, b1_id = borrower_one

    r = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": b1_id,
            "loan_amount": 10000.0,
            "loan_date": "2026-10-01",
            "total_payable": 12000.0,
            "minimum_monthly_payment": 1000.0,
            "notes": "Module 4 Payment Test Loan",
        },
    )
    assert r.status_code == 201
    return r.json()["id"]


# ── 1. Submission Tests ──────────────────────────────────────────────

def test_borrower_can_submit_payment_success(borrower_one, loan_for_b1):
    """Borrower submits a valid payment against their own loan."""
    token, _ = borrower_one
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "1500.00",
        "payment_month": "2026-10",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["status"] == "PENDING"
    assert Decimal(str(res["amount"])) == Decimal("1500.00")
    assert res["loan_id"] == loan_for_b1
    assert res["payment_month"] == "2026-10"
    assert res["screenshot_url"] is not None
    assert res["verified_at"] is None
    assert res["verified_by"] is None


def test_pending_payment_does_not_affect_loan_balance(admin_user, loan_for_b1):
    """Pending payments must NEVER reduce remaining balance."""
    admin_token, _ = admin_user
    r = client.get(
        f"/loans/{loan_for_b1}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    res = r.json()
    # Loan was 12000.00 total payable, remaining balance must still be 12000.00
    assert Decimal(str(res["remaining_balance"])) == Decimal("12000.00")
    assert Decimal(str(res["total_paid"])) == Decimal("0.00")


def test_borrower_cannot_submit_payment_for_another_borrowers_loan(borrower_two, loan_for_b1):
    """Borrower 2 attempts to submit a payment against Borrower 1's loan."""
    token, _ = borrower_two
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "500.00",
        "payment_month": "2026-10",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 403


def test_payment_amount_must_be_greater_than_zero(borrower_one, loan_for_b1):
    """Amount <= 0 is rejected."""
    token, _ = borrower_one
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "0.00",
        "payment_month": "2026-10",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 422 or r.status_code == 400


def test_payment_amount_cannot_exceed_remaining_balance(borrower_one, loan_for_b1):
    """Amount > remaining balance is rejected."""
    token, _ = borrower_one
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "99999.00",  # remaining is 12000
        "payment_month": "2026-10",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 400
    assert "exceed" in r.json()["detail"].lower()


def test_invalid_screenshot_file_type_rejected(borrower_one, loan_for_b1):
    """Non-image files (e.g. .pdf or .exe) are rejected."""
    token, _ = borrower_one
    files = {"screenshot": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "500.00",
        "payment_month": "2026-10",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower() or "invalid" in r.json()["detail"].lower()


def test_invalid_payment_month_format_rejected(borrower_one, loan_for_b1):
    """Invalid month formats (e.g. 'October 2026') are rejected."""
    token, _ = borrower_one
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "loan_id": loan_for_b1,
        "amount": "500.00",
        "payment_month": "invalid-month",
        "payment_date": "2026-10-04",
    }

    r = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 400


# ── 2. Admin Verification & Approval Tests ───────────────────────────

def test_admin_can_list_pending_payments(admin_user):
    """Admin can query GET /payments/pending."""
    admin_token, _ = admin_user
    r = client.get(
        "/payments/pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    res = r.json()
    assert isinstance(res, list)
    assert len(res) >= 1
    assert any(p["status"] == "PENDING" for p in res)


def test_borrower_cannot_list_pending_payments(borrower_one):
    """Borrower accessing /payments/pending gets 403 Forbidden."""
    token, _ = borrower_one
    r = client.get(
        "/payments/pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_admin_can_approve_payment_and_reduce_balance(admin_user, borrower_one, loan_for_b1):
    """Admin approves pending payment: status becomes VERIFIED and loan balance decreases."""
    admin_token, admin_id = admin_user
    b1_token, _ = borrower_one

    # 1. Submit a payment of 2000.00
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "2000.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    assert sub_res.status_code == 201
    payment_id = sub_res.json()["id"]

    # 2. Admin approves the payment
    app_res = client.post(
        f"/payments/{payment_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert app_res.status_code == 200, app_res.text
    p_data = app_res.json()["payment"]
    assert p_data["status"] == "VERIFIED"
    assert p_data["verified_at"] is not None
    assert p_data["verified_by"] == admin_id

    # 3. Check loan balance: 12000 - 2000 = 10000 remaining
    loan_res = client.get(
        f"/loans/{loan_for_b1}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert Decimal(str(loan_res.json()["remaining_balance"])) == Decimal("10000.00")
    assert Decimal(str(loan_res.json()["total_paid"])) == Decimal("2000.00")


def test_admin_cannot_approve_same_payment_twice(admin_user, borrower_one, loan_for_b1):
    """Double approval on already VERIFIED payment returns 400."""
    admin_token, _ = admin_user
    b1_token, _ = borrower_one

    # Submit and approve
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "500.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # First approval -> 200
    r1 = client.post(
        f"/payments/{payment_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200

    # Second approval -> 400
    r2 = client.post(
        f"/payments/{payment_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 400
    assert "already verified" in r2.json()["detail"].lower()


# ── 3. Admin Rejection Tests ─────────────────────────────────────────

def test_admin_can_reject_payment_with_reason(admin_user, borrower_one, loan_for_b1):
    """Admin rejects a payment with explanation; balance is unchanged."""
    admin_token, _ = admin_user
    b1_token, _ = borrower_one

    # Balance before
    l_before = client.get(f"/loans/{loan_for_b1}", headers={"Authorization": f"Bearer {admin_token}"}).json()
    rem_before = Decimal(str(l_before["remaining_balance"]))

    # Submit payment
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "1000.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # Reject payment
    reason = "Transaction reference ID not visible in screenshot"
    rej_res = client.post(
        f"/payments/{payment_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": reason},
    )
    assert rej_res.status_code == 200
    rej_data = rej_res.json()
    assert rej_data["status"] == "REJECTED"
    assert rej_data["rejection_reason"] == reason
    assert rej_data["verified_at"] is None
    assert rej_data["verified_by"] is None

    # Balance after rejection must be unchanged
    l_after = client.get(f"/loans/{loan_for_b1}", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert Decimal(str(l_after["remaining_balance"])) == rem_before


def test_cannot_approve_rejected_payment(admin_user, borrower_one, loan_for_b1):
    """REJECTED -> VERIFIED transition is rejected."""
    admin_token, _ = admin_user
    b1_token, _ = borrower_one

    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "500.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # Reject
    client.post(
        f"/payments/{payment_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": "Invalid transfer"},
    )

    # Attempt approve
    app_res = client.post(
        f"/payments/{payment_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert app_res.status_code == 400


def test_cannot_reject_verified_payment(admin_user, borrower_one, loan_for_b1):
    """VERIFIED -> REJECTED transition is rejected."""
    admin_token, _ = admin_user
    b1_token, _ = borrower_one

    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "500.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # Approve
    client.post(
        f"/payments/{payment_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Attempt reject
    rej_res = client.post(
        f"/payments/{payment_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"rejection_reason": "Mistake"},
    )
    assert rej_res.status_code == 400


# ── 4. Final Payment & Auto-Closure to PAID ──────────────────────────

def test_final_payment_marks_loan_as_paid(admin_user, borrower_two):
    """When a verified payment clears remaining balance to 0, loan status becomes PAID."""
    admin_token, _ = admin_user
    b2_token, b2_id = borrower_two

    # Create a small loan of total_payable = 1000
    create_l = client.post(
        "/loans",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "borrower_id": b2_id,
            "loan_amount": 800.0,
            "loan_date": "2026-10-01",
            "total_payable": 1000.0,
            "minimum_monthly_payment": 500.0,
        },
    )
    assert create_l.status_code == 201
    small_loan_id = create_l.json()["id"]

    # Submit payment for exact remaining amount: 1000.00
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b2_token}"},
        data={
            "loan_id": small_loan_id,
            "amount": "1000.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    assert sub_res.status_code == 201
    pay_id = sub_res.json()["id"]

    # Approve payment
    app_res = client.post(
        f"/payments/{pay_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["loan_status"] == "PAID"
    assert Decimal(str(app_res.json()["new_remaining_balance"])) == Decimal("0.00")

    # Verify loan details
    loan_check = client.get(
        f"/loans/{small_loan_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert loan_check["status"] == "PAID"
    assert Decimal(str(loan_check["remaining_balance"])) == Decimal("0.00")

    # Submitting another payment to a PAID loan must fail
    files2 = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    extra_sub = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b2_token}"},
        data={
            "loan_id": small_loan_id,
            "amount": "100.00",
            "payment_month": "2026-11",
            "payment_date": "2026-11-01",
        },
        files=files2,
    )
    assert extra_sub.status_code == 400


# ── 5. Payment History & Screenshot Security ─────────────────────────

def test_borrower_can_view_own_payment_history(borrower_one):
    """Borrower can fetch /my/payments and view their own submissions."""
    token, _ = borrower_one
    r = client.get("/my/payments", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    res = r.json()
    assert isinstance(res, list)
    assert len(res) >= 1


def test_borrower_can_view_own_payment_screenshot(borrower_one, loan_for_b1):
    """Borrower can stream their own screenshot."""
    token, _ = borrower_one
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "100.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # Fetch screenshot
    r = client.get(
        f"/payments/{payment_id}/screenshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] in ["image/png", "image/jpeg"]


def test_borrower_cannot_view_another_borrowers_screenshot(borrower_one, borrower_two, loan_for_b1):
    """Borrower 2 cannot access Borrower 1's screenshot proof."""
    b1_token, _ = borrower_one
    b2_token, _ = borrower_two

    # B1 submits payment
    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "200.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    # B2 attempts to view B1's screenshot
    r = client.get(
        f"/payments/{payment_id}/screenshot",
        headers={"Authorization": f"Bearer {b2_token}"},
    )
    assert r.status_code == 403


def test_admin_can_view_any_payment_screenshot(admin_user, borrower_one, loan_for_b1):
    """Admin can view any uploaded screenshot."""
    admin_token, _ = admin_user
    b1_token, _ = borrower_one

    files = {"screenshot": ("proof.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    sub_res = client.post(
        "/payments",
        headers={"Authorization": f"Bearer {b1_token}"},
        data={
            "loan_id": loan_for_b1,
            "amount": "250.00",
            "payment_month": "2026-10",
            "payment_date": "2026-10-04",
        },
        files=files,
    )
    payment_id = sub_res.json()["id"]

    r = client.get(
        f"/payments/{payment_id}/screenshot",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200


def test_unauthenticated_requests_blocked():
    """Unauthenticated access to payment APIs returns 401."""
    assert client.get("/my/payments").status_code == 401
    assert client.get("/payments/pending").status_code == 401
    assert client.post("/payments/1/approve").status_code == 401
    assert client.post("/payments/1/reject", json={"rejection_reason": "No"}).status_code == 401
