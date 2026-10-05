"""
Loan management routes.

- Admin endpoints: CRUD on all loans + dashboard stats
- Borrower endpoints: read-only access to own loans + dashboard stats
"""

import logging
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger("loantracker.loans")

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.loan import Loan, LoanStatus
from app.models.user import User, UserRole
from app.schemas.loan import (
    LoanCreate,
    LoanUpdate,
    LoanResponse,
    LoanSummary,
    BorrowerLoanResponse,
    AdminDashboardStats,
    BorrowerDashboardStats,
)
from app.services.loan_service import (
    enrich_loan_dict,
    get_total_paid,
    get_admin_dashboard_stats,
    get_borrower_dashboard_stats,
)


# ── Admin loan routes ───────────────────────────────────────────────
admin_router = APIRouter(
    prefix="/loans",
    tags=["Loan Management (Admin)"],
    dependencies=[Depends(require_admin)],
)


@admin_router.post("", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
def create_loan(payload: LoanCreate, db: Session = Depends(get_db)):
    """Create a new loan for an active borrower. Admin only."""
    borrower = db.query(User).filter(User.id == payload.borrower_id).first()

    if not borrower:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower not found")
    if borrower.role != UserRole.BORROWER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loans can only be assigned to users with BORROWER role",
        )
    if not borrower.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a loan for a deactivated borrower",
        )

    new_loan = Loan(
        borrower_id=payload.borrower_id,
        loan_amount=payload.loan_amount,
        loan_date=payload.loan_date,
        total_payable=payload.total_payable,
        minimum_monthly_payment=payload.minimum_monthly_payment,
        notes=payload.notes,
        status=LoanStatus.ACTIVE,
    )
    db.add(new_loan)
    db.commit()
    db.refresh(new_loan)

    # Dispatch New Loan Email to borrower
    if borrower.email:
        try:
            from app.services.email_service import send_new_loan_email
            ok, err = send_new_loan_email(
                borrower_name=borrower.name,
                borrower_email=borrower.email,
                loan_id=new_loan.id,
                loan_amount=float(new_loan.loan_amount),
                total_payable=float(new_loan.total_payable),
                minimum_monthly_payment=float(new_loan.minimum_monthly_payment),
                loan_date=str(new_loan.loan_date),
                notes=new_loan.notes,
            )
            if ok:
                logger.info(f"New loan email sent to {borrower.email} for loan #{new_loan.id}")
            else:
                logger.error(f"New loan email failed for {borrower.email}: {err}")
        except Exception as e:
            logger.error(f"Exception sending loan email to {borrower.email}: {e}")
    else:
        logger.warning(f"Borrower {borrower.name} has no email - skipping loan notification")

    return enrich_loan_dict(db, new_loan)


@admin_router.get("", response_model=List[LoanSummary])
def list_loans(db: Session = Depends(get_db)):
    """List all loans with computed balances. Admin only."""
    loans = (
        db.query(Loan)
        .order_by(Loan.created_at.desc())
        .all()
    )
    return [enrich_loan_dict(db, loan) for loan in loans]


@admin_router.get("/stats", response_model=AdminDashboardStats)
def admin_dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregate dashboard statistics. Admin only."""
    return get_admin_dashboard_stats(db)


@admin_router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(loan_id: int, db: Session = Depends(get_db)):
    """Get full details for a single loan. Admin only."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return enrich_loan_dict(db, loan)


@admin_router.put("/{loan_id}", response_model=LoanResponse)
def update_loan(loan_id: int, payload: LoanUpdate, db: Session = Depends(get_db)):
    """
    Update loan information. Admin only.
    Prevents setting total_payable below already-verified payments.
    """
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    total_paid = get_total_paid(db, loan.id)

    # Validate total_payable change
    new_total_payable = payload.total_payable if payload.total_payable is not None else loan.total_payable
    if new_total_payable < total_paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot set total_payable below already verified payments ({total_paid})",
        )

    if payload.loan_amount is not None:
        loan.loan_amount = payload.loan_amount
    if payload.loan_date is not None:
        loan.loan_date = payload.loan_date
    if payload.total_payable is not None:
        loan.total_payable = payload.total_payable
    if payload.minimum_monthly_payment is not None:
        loan.minimum_monthly_payment = payload.minimum_monthly_payment
    if payload.notes is not None:
        loan.notes = payload.notes
    if payload.status is not None:
        loan.status = payload.status

    db.commit()
    db.refresh(loan)

    return enrich_loan_dict(db, loan)


@admin_router.delete("/{loan_id}", status_code=status.HTTP_200_OK)
def delete_loan(loan_id: int, db: Session = Depends(get_db)):
    """
    Permanently delete a loan and all its associated payments. Admin only.
    """
    from app.models.payment import Payment

    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    # Delete all payment records associated with this loan
    db.query(Payment).filter(Payment.loan_id == loan_id).delete()
    db.delete(loan)
    db.commit()

    return {"detail": "Loan and associated payments deleted successfully"}



# ── Borrower loan routes ────────────────────────────────────────────
borrower_router = APIRouter(
    prefix="/my",
    tags=["My Loans (Borrower)"],
)


@borrower_router.get("/loans", response_model=List[BorrowerLoanResponse])
def my_loans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the authenticated borrower's own loans."""
    loans = (
        db.query(Loan)
        .filter(Loan.borrower_id == current_user.id)
        .order_by(Loan.created_at.desc())
        .all()
    )
    return [enrich_loan_dict(db, loan) for loan in loans]


@borrower_router.get("/loans/{loan_id}", response_model=BorrowerLoanResponse)
def my_loan_detail(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detail for a specific loan belonging to the authenticated borrower."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan or loan.borrower_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return enrich_loan_dict(db, loan)


@borrower_router.get("/stats", response_model=BorrowerDashboardStats)
def my_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregate statistics for the authenticated borrower's dashboard."""
    return get_borrower_dashboard_stats(db, current_user.id)
