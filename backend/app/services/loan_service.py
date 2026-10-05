"""
Loan business-logic service layer.

Encapsulates balance calculations and loan lifecycle operations,
keeping route handlers thin.
"""

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole


def get_total_paid(db: Session, loan_id: int) -> Decimal:
    """
    Calculate total verified payments for a specific loan.
    Only VERIFIED payments count.
    """
    result = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.loan_id == loan_id,
            Payment.status == PaymentStatus.VERIFIED,
        )
        .scalar()
    )
    return Decimal(str(result))


def get_remaining_balance(db: Session, loan: Loan) -> Decimal:
    """Remaining = total_payable - sum(verified payments)."""
    paid = get_total_paid(db, loan.id)
    remaining = loan.total_payable - paid
    return max(remaining, Decimal("0.00"))


def enrich_loan_dict(db: Session, loan: Loan) -> dict:
    """
    Build a dictionary from a Loan ORM object with computed
    total_paid and remaining_balance fields attached.
    """
    total_paid = get_total_paid(db, loan.id)
    remaining = max(loan.total_payable - total_paid, Decimal("0.00"))
    return {
        "id": loan.id,
        "borrower_id": loan.borrower_id,
        "borrower": loan.borrower,
        "loan_amount": loan.loan_amount,
        "loan_date": loan.loan_date,
        "total_payable": loan.total_payable,
        "minimum_monthly_payment": loan.minimum_monthly_payment,
        "total_paid": total_paid,
        "remaining_balance": remaining,
        "status": loan.status,
        "notes": loan.notes,
        "created_at": loan.created_at,
        "updated_at": loan.updated_at,
    }


def get_admin_dashboard_stats(db: Session) -> dict:
    """Aggregate statistics for the admin dashboard."""
    total_borrowers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.BORROWER)
        .scalar()
    )

    active_loans_q = db.query(Loan).filter(Loan.status == LoanStatus.ACTIVE).all()
    active_loans_count = len(active_loans_q)

    total_amount_lent = (
        db.query(func.coalesce(func.sum(Loan.loan_amount), 0))
        .filter(Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.PAID]))
        .scalar()
    )

    # Total outstanding = sum of remaining balances of active loans
    total_outstanding = Decimal("0.00")
    for loan in active_loans_q:
        remaining = get_remaining_balance(db, loan)
        total_outstanding += remaining

    return {
        "total_borrowers": total_borrowers,
        "active_loans": active_loans_count,
        "total_amount_lent": Decimal(str(total_amount_lent)),
        "total_outstanding": total_outstanding,
    }


def get_borrower_dashboard_stats(db: Session, borrower_id: int) -> dict:
    """Aggregate statistics for a borrower's dashboard."""
    active_loans = (
        db.query(Loan)
        .filter(Loan.borrower_id == borrower_id, Loan.status == LoanStatus.ACTIVE)
        .all()
    )

    total_outstanding = Decimal("0.00")
    for loan in active_loans:
        total_outstanding += get_remaining_balance(db, loan)

    return {
        "active_loans": len(active_loans),
        "total_outstanding": total_outstanding,
    }
