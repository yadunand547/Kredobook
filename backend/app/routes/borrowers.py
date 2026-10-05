"""
Borrower management routes - accessible exclusively by ADMIN users.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger("loantracker.borrowers")

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User, UserRole
from app.schemas.user import BorrowerCreate, BorrowerUpdate, UserOut
from app.utils.security import hash_password

router = APIRouter(
    prefix="/borrowers",
    tags=["Borrower Management (Admin Only)"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_borrower(
    borrower_data: BorrowerCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new borrower account.
    Admin-only endpoint. Hashes the initial password and assigns BORROWER role.
    """
    # Check for duplicate email
    existing_user = db.query(User).filter(User.email == borrower_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Hash the password
    password_hash = hash_password(borrower_data.password)

    new_borrower = User(
        name=borrower_data.name,
        email=borrower_data.email,
        phone=borrower_data.phone,
        password_hash=password_hash,
        role=UserRole.BORROWER,
        is_active=True,
        monthly_reminder_enabled=borrower_data.monthly_reminder_enabled if borrower_data.monthly_reminder_enabled is not None else True,
    )

    db.add(new_borrower)
    db.commit()
    db.refresh(new_borrower)

    # Dispatch Welcome Email to borrower
    if new_borrower.email:
        try:
            from app.services.email_service import send_welcome_email
            ok, err = send_welcome_email(
                borrower_name=new_borrower.name,
                borrower_email=new_borrower.email,
                password=borrower_data.password,
            )
            if ok:
                logger.info(f"Welcome email sent to {new_borrower.email}")
            else:
                logger.error(f"Welcome email failed for {new_borrower.email}: {err}")
        except Exception as e:
            logger.error(f"Exception sending welcome email to {new_borrower.email}: {e}")
    else:
        logger.warning(f"Borrower {new_borrower.name} has no email - skipping welcome email")

    return new_borrower


@router.get("", response_model=List[UserOut])
def list_borrowers(db: Session = Depends(get_db)):
    """
    List all borrowers in the system.
    Admin-only endpoint. Never exposes password hashes.
    """
    borrowers = (
        db.query(User)
        .filter(User.role == UserRole.BORROWER)
        .order_by(User.created_at.desc())
        .all()
    )
    return borrowers


@router.get("/{borrower_id}", response_model=UserOut)
def get_borrower(borrower_id: int, db: Session = Depends(get_db)):
    """
    Retrieve details for a specific borrower.
    Admin-only endpoint.
    """
    borrower = (
        db.query(User)
        .filter(User.id == borrower_id, User.role == UserRole.BORROWER)
        .first()
    )

    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found",
        )

    return borrower


@router.put("/{borrower_id}", response_model=UserOut)
def update_borrower(
    borrower_id: int,
    borrower_update: BorrowerUpdate,
    db: Session = Depends(get_db),
):
    """
    Update borrower personal information or active status.
    Admin-only endpoint. Role change is prevented.
    """
    borrower = (
        db.query(User)
        .filter(User.id == borrower_id, User.role == UserRole.BORROWER)
        .first()
    )

    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found",
        )

    # If updating email, ensure it doesn't conflict with another user
    if borrower_update.email and borrower_update.email != borrower.email:
        email_conflict = (
            db.query(User)
            .filter(User.email == borrower_update.email, User.id != borrower_id)
            .first()
        )
        if email_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        borrower.email = borrower_update.email

    if borrower_update.name is not None:
        borrower.name = borrower_update.name

    if borrower_update.phone is not None:
        borrower.phone = borrower_update.phone

    if borrower_update.is_active is not None:
        borrower.is_active = borrower_update.is_active

    if borrower_update.monthly_reminder_enabled is not None:
        borrower.monthly_reminder_enabled = borrower_update.monthly_reminder_enabled

    db.commit()

    db.refresh(borrower)

    return borrower


@router.delete("/{borrower_id}", response_model=UserOut)
def deactivate_borrower(borrower_id: int, db: Session = Depends(get_db)):
    """
    Soft-deactivates a borrower (sets is_active = False).
    Admin-only endpoint. Preserves historical records.
    """
    borrower = (
        db.query(User)
        .filter(User.id == borrower_id, User.role == UserRole.BORROWER)
        .first()
    )

    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found",
        )

    borrower.is_active = False
    db.commit()
    db.refresh(borrower)

    return borrower


@router.delete("/{borrower_id}/permanent", status_code=status.HTTP_200_OK)
def delete_borrower_permanently(borrower_id: int, db: Session = Depends(get_db)):
    """
    Permanently delete a borrower and all associated loans, payments, and reminders.
    Admin-only endpoint.
    """
    from app.models.loan import Loan
    from app.models.payment import Payment
    from app.models.reminder import ReminderLog

    borrower = (
        db.query(User)
        .filter(User.id == borrower_id, User.role == UserRole.BORROWER)
        .first()
    )

    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found",
        )

    # Clean up reminder logs
    db.query(ReminderLog).filter(ReminderLog.borrower_id == borrower_id).delete()

    # Clean up payments and loans
    loans = db.query(Loan).filter(Loan.borrower_id == borrower_id).all()
    for l in loans:
        db.query(Payment).filter(Payment.loan_id == l.id).delete()
        db.delete(l)

    db.delete(borrower)
    db.commit()

    return {"detail": "Borrower and associated loans/payments deleted successfully"}

