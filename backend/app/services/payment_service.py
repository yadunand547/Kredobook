"""
Payment business logic service layer.

Handles:
- Borrower payment submission with validation against loan balance and ownership
- Admin payment approval with balance recomputation and loan auto-closure
- Admin payment rejection with reason
- Concurrency-safe transitions
"""

import re
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.services.loan_service import get_remaining_balance, get_total_paid

PAYMENT_MONTH_REGEX = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def create_payment(
    db: Session,
    borrower: User,
    loan_id: int,
    amount: Decimal,
    payment_month: str,
    payment_date: datetime | date,
    screenshot_filename: str,
) -> Payment:
    """
    Validate and create a PENDING payment for the authenticated borrower.
    """
    # 1. Validate loan exists
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan not found",
        )

    # 2. Validate loan ownership
    if loan.borrower_id != borrower.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to submit payments for this loan",
        )

    # 3. Validate loan status
    if loan.status == LoanStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit payments for a fully paid loan",
        )
    if loan.status == LoanStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit payments for a cancelled loan",
        )

    # 4. Validate remaining balance and amount
    remaining = get_remaining_balance(db, loan)
    if remaining <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loan is already fully paid (zero remaining balance)",
        )

    if amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be greater than zero",
        )

    if amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount (₹{amount:,.2f}) cannot exceed current remaining balance (₹{remaining:,.2f})",
        )

    # 5. Validate payment month format (YYYY-MM)
    if not payment_month or not PAYMENT_MONTH_REGEX.match(payment_month.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment_month format. Expected format: YYYY-MM (e.g. 2026-10)",
        )

    # 6. Normalize payment date to timezone-aware datetime
    if isinstance(payment_date, date) and not isinstance(payment_date, datetime):
        norm_payment_date = datetime.combine(payment_date, datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(payment_date, datetime):
        if payment_date.tzinfo is None:
            norm_payment_date = payment_date.replace(tzinfo=timezone.utc)
        else:
            norm_payment_date = payment_date
    else:
        norm_payment_date = datetime.now(timezone.utc)

    # 7. Create Payment record with PENDING status
    new_payment = Payment(
        loan_id=loan.id,
        borrower_id=borrower.id,
        amount=amount,
        payment_month=payment_month.strip(),
        payment_date=norm_payment_date,
        screenshot_url=screenshot_filename,
        status=PaymentStatus.PENDING,
        submitted_at=datetime.now(timezone.utc),
        verified_at=None,
        verified_by=None,
        rejection_reason=None,
    )

    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    return new_payment


def approve_payment(
    db: Session,
    payment_id: int,
    admin_user: User,
) -> Tuple[Payment, Loan, Decimal]:
    """
    Approve a pending payment safely within a database transaction.

    Transitions: PENDING -> VERIFIED
    Updates loan balance. If balance hits 0, auto-marks loan as PAID.
    """
    # Load payment
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # State machine checks
    if payment.status == PaymentStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already verified",
        )
    if payment.status == PaymentStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already rejected and cannot be approved",
        )
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve payment with status '{payment.status}'",
        )

    # Load associated loan
    loan = db.query(Loan).filter(Loan.id == payment.loan_id).first()
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated loan not found",
        )

    # Re-verify remaining balance before this approval
    current_paid = get_total_paid(db, loan.id)
    current_remaining = loan.total_payable - current_paid

    if payment.amount > current_remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount (₹{payment.amount:,.2f}) exceeds current loan remaining balance (₹{current_remaining:,.2f})",
        )

    # Perform atomic update
    payment.status = PaymentStatus.VERIFIED
    payment.verified_at = datetime.now(timezone.utc)
    payment.verified_by = admin_user.id
    payment.rejection_reason = None

    # Recalculate remaining balance including this newly verified payment
    new_total_paid = current_paid + payment.amount
    new_remaining = loan.total_payable - new_total_paid

    if new_remaining <= Decimal("0.00"):
        new_remaining = Decimal("0.00")
        loan.status = LoanStatus.PAID

    db.commit()
    db.refresh(payment)
    db.refresh(loan)

    return payment, loan, new_remaining


def reject_payment(
    db: Session,
    payment_id: int,
    admin_user: User,
    rejection_reason: str,
) -> Payment:
    """
    Reject a pending payment with an admin explanation.

    Transitions: PENDING -> REJECTED
    Loan balance remains unchanged.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.status == PaymentStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already verified payment",
        )
    if payment.status == PaymentStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already rejected",
        )
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject payment with status '{payment.status}'",
        )

    if not rejection_reason or not rejection_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required",
        )

    payment.status = PaymentStatus.REJECTED
    payment.rejection_reason = rejection_reason.strip()
    payment.verified_at = None
    payment.verified_by = None

    db.commit()
    db.refresh(payment)

    return payment
