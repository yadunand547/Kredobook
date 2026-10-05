"""
CLI script to safely seed/create an initial admin account.

Usage:
    python scripts/create_admin.py
    python scripts/create_admin.py --email admin@example.com --name "System Admin" --password secret
"""

import argparse
import getpass
import os
import sys

# Ensure backend root is on python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import hash_password


def create_or_update_admin(name: str, email: str, password: str, update: bool = False):
    """Create or update an admin account securely."""
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == email).first()

        if existing_user:
            if not update:
                print(f"[!] User with email '{email}' already exists with role '{existing_user.role.value}'.")
                print("    Use --update to overwrite the password and promote to ADMIN.")
                return False
            
            print(f"[*] Updating existing user '{email}' to ADMIN...")
            existing_user.name = name or existing_user.name
            existing_user.password_hash = hash_password(password)
            existing_user.role = UserRole.ADMIN
            existing_user.is_active = True
            db.commit()
            print(f"[+] Admin account '{email}' updated successfully.")
            return True

        hashed_pw = hash_password(password)
        new_admin = User(
            name=name,
            email=email,
            password_hash=hashed_pw,
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        print(f"[+] Admin user '{new_admin.email}' (ID: {new_admin.id}) created successfully.")
        return True
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or seed an initial admin account.")
    parser.add_argument("--name", help="Full name of the admin", default=os.getenv("ADMIN_NAME"))
    parser.add_argument("--email", help="Admin email address", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--password", help="Admin password (plaintext)", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--update", action="store_true", help="Update existing account password and role to ADMIN")

    args = parser.parse_args()

    name = args.name
    email = args.email
    password = args.password

    # Prompt interactively if not provided
    if not email:
        email = input("Enter admin email: ").strip()
    if not name:
        name = input("Enter admin full name [System Admin]: ").strip() or "System Admin"
    if not password:
        password = getpass.getpass("Enter admin password: ").strip()
        confirm_password = getpass.getpass("Confirm admin password: ").strip()
        if password != confirm_password:
            print("[!] Passwords do not match. Aborting.")
            sys.exit(1)

    if not email or not password:
        print("[!] Email and password are required.")
        sys.exit(1)

    success = create_or_update_admin(name=name, email=email, password=password, update=args.update)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
