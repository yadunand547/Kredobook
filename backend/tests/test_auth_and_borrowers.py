"""
Comprehensive integration tests for Module 2: Authentication and Borrower Management.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_credentials():
    """Ensure an admin account exists and return its credentials."""
    email = "test_admin@example.com"
    password = "TestAdminPass123!"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name="Test Admin",
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
            user.role = UserRole.ADMIN
            user.is_active = True
            db.commit()
    finally:
        db.close()

    return {"email": email, "password": password}


@pytest.fixture(scope="module")
def admin_token(admin_credentials):
    """Authenticate as admin and return JWT access token."""
    response = client.post("/auth/login", json=admin_credentials)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"
    return data["access_token"]


def test_login_invalid_password(admin_credentials):
    """Test login failure with wrong password."""
    response = client.post(
        "/auth/login",
        json={"email": admin_credentials["email"], "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user():
    """Test login failure with unregistered email."""
    response = client.post(
        "/auth/login",
        json={"email": f"unknown_{uuid.uuid4().hex[:6]}@example.com", "password": "any"},
    )
    assert response.status_code == 401


def test_get_me_success(admin_token, admin_credentials):
    """Test /auth/me returns current user profile."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == admin_credentials["email"]
    assert data["role"] == "ADMIN"
    assert "password" not in data
    assert "password_hash" not in data


def test_get_me_unauthorized():
    """Test /auth/me rejects requests without token."""
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)


def test_borrower_management_lifecycle(admin_token):
    """
    Test complete lifecycle:
    1. Admin creates borrower
    2. Admin lists borrowers
    3. Admin views borrower
    4. Admin updates borrower
    5. Borrower logs in successfully
    6. Borrower cannot access admin routes (authorization check)
    7. Admin deactivates borrower
    8. Deactivated borrower cannot log in
    """
    unique_suffix = uuid.uuid4().hex[:8]
    borrower_email = f"borrower_{unique_suffix}@example.com"
    borrower_password = "BorrowerPass123!"

    # 1. Admin creates borrower
    create_payload = {
        "name": f"Borrower {unique_suffix}",
        "email": borrower_email,
        "phone": "555-0199",
        "password": borrower_password,
    }
    create_res = client.post(
        "/borrowers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=create_payload,
    )
    assert create_res.status_code == 201
    borrower_data = create_res.json()
    borrower_id = borrower_data["id"]
    assert borrower_data["email"] == borrower_email
    assert borrower_data["role"] == "BORROWER"
    assert borrower_data["is_active"] is True
    assert "password" not in borrower_data
    assert "password_hash" not in borrower_data

    # 1b. Duplicate email creation should fail with 409
    dup_res = client.post(
        "/borrowers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=create_payload,
    )
    assert dup_res.status_code == 409

    # 2. Admin lists borrowers
    list_res = client.get(
        "/borrowers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_res.status_code == 200
    borrowers_list = list_res.json()
    assert any(b["id"] == borrower_id for b in borrowers_list)

    # 3. Admin gets borrower details
    get_res = client.get(
        f"/borrowers/{borrower_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == borrower_id

    # 4. Admin updates borrower info
    update_res = client.put(
        f"/borrowers/{borrower_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Updated Borrower {unique_suffix}", "phone": "555-9999"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == f"Updated Borrower {unique_suffix}"
    assert update_res.json()["phone"] == "555-9999"

    # 5. Borrower logs in
    login_res = client.post(
        "/auth/login",
        json={"email": borrower_email, "password": borrower_password},
    )
    assert login_res.status_code == 200
    borrower_token = login_res.json()["access_token"]
    assert login_res.json()["user"]["role"] == "BORROWER"

    # 6. Borrower CANNOT access admin-only APIs (Authorization check)
    # Cannot list borrowers
    forbidden_list = client.get(
        "/borrowers",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    assert forbidden_list.status_code == 403

    # Cannot view another borrower
    forbidden_get = client.get(
        f"/borrowers/{borrower_id}",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    assert forbidden_get.status_code == 403

    # Cannot create borrower
    forbidden_create = client.post(
        "/borrowers",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={"name": "Hacker", "email": "h@test.com", "password": "pass"},
    )
    assert forbidden_create.status_code == 403

    # But borrower CAN access their own /auth/me
    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == borrower_email

    # 7. Admin deactivates borrower
    deact_res = client.delete(
        f"/borrowers/{borrower_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 8. Deactivated borrower cannot log in
    deact_login = client.post(
        "/auth/login",
        json={"email": borrower_email, "password": borrower_password},
    )
    assert deact_login.status_code == 401
    assert "deactivated" in deact_login.json()["detail"].lower()

    # Deactivated borrower's existing token is also rejected by dependencies
    deact_me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    assert deact_me.status_code == 401
