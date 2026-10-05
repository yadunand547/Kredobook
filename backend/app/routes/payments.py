"""
Payment submission, verification, and history API routes.

- Admin routes: list pending, approve, reject, view loan payment history
- Borrower routes: submit payment, list own payments, view loan payment history
- Shared secured routes: view single payment detail, stream screenshot image
"""

import mimetypes
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_borrower
from app.models.loan import Loan
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.payment import (
    PaymentReject,
    PaymentResponse,
    PaymentVerificationResponse,
    AdminPastPaymentUpdate,
)
from app.services.payment_service import (
    approve_payment,
    create_payment,
    reject_payment,
)
from app.utils.storage import get_screenshot_path, save_screenshot

router = APIRouter(tags=["Payment Management"])


# ── Borrower: Submit Payment ─────────────────────────────────────────
@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_borrower)],
)
async def submit_payment(
    loan_id: int = Form(..., description="ID of the loan being paid"),
    amount: Decimal = Form(..., gt=0, description="Actual payment amount"),
    payment_month: str = Form(..., description="Month payment is for, format YYYY-MM"),
    payment_date: str = Form(..., description="Date money was transferred, format YYYY-MM-DD"),
    screenshot: UploadFile = File(..., description="Proof screenshot file (PNG, JPG, WEBP)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a payment for verification. Borrower only.
    Uploads screenshot and creates a PENDING payment record.
    """
    # 1. Parse payment date
    try:
        parsed_date = date.fromisoformat(payment_date.strip())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment_date format. Expected YYYY-MM-DD (e.g. 2026-10-04)",
        )

    # 2. Save screenshot securely
    saved_filename = await save_screenshot(screenshot)

    # 3. Create payment record
    new_payment = create_payment(
        db=db,
        borrower=current_user,
        loan_id=loan_id,
        amount=amount,
        payment_month=payment_month,
        payment_date=parsed_date,
        screenshot_filename=saved_filename,
    )

    return new_payment


# ── Admin: List Payments (with optional status filter) ──────────────
@router.get(
    "/payments",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)],
)
def list_all_payments(
    status: Optional[PaymentStatus] = None,
    db: Session = Depends(get_db),
):
    """List all payments with optional status filter. Admin only."""
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status)
    payments = query.order_by(Payment.submitted_at.desc()).all()
    return payments


# ── Admin: List Pending Payments ─────────────────────────────────────
@router.get(
    "/payments/pending",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)],
)
def list_pending_payments(db: Session = Depends(get_db)):
    """List all payments awaiting verification. Admin only."""
    payments = (
        db.query(Payment)
        .filter(Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.submitted_at.asc())
        .all()
    )
    return payments



# ── Admin: Approve Payment ───────────────────────────────────────────
@router.post(
    "/payments/{payment_id}/approve",
    response_model=PaymentVerificationResponse,
    dependencies=[Depends(require_admin)],
)
def approve_payment_endpoint(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Approve a pending payment. Admin only.
    Transitions status to VERIFIED, reduces loan balance, and marks loan PAID if cleared.
    """
    payment, loan, new_remaining = approve_payment(
        db=db,
        payment_id=payment_id,
        admin_user=current_user,
    )
    return {
        "payment": payment,
        "loan_id": loan.id,
        "loan_status": loan.status.value,
        "new_remaining_balance": new_remaining,
        "message": f"Payment #{payment.id} verified successfully. Remaining balance: ₹{new_remaining:,.2f}",
    }


# ── Admin: Reject Payment ────────────────────────────────────────────
@router.post(
    "/payments/{payment_id}/reject",
    response_model=PaymentResponse,
    dependencies=[Depends(require_admin)],
)
def reject_payment_endpoint(
    payment_id: int,
    payload: PaymentReject,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reject a pending payment with a stated reason. Admin only.
    Transitions status to REJECTED. Loan balance remains unchanged.
    """
    payment = reject_payment(
        db=db,
        payment_id=payment_id,
        admin_user=current_user,
        rejection_reason=payload.rejection_reason,
    )
    return payment


# ── Borrower: My Payments ───────────────────────────────────────────
@router.get(
    "/my/payments",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_borrower)],
)
def get_my_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all payment records submitted by the authenticated borrower."""
    payments = (
        db.query(Payment)
        .filter(Payment.borrower_id == current_user.id)
        .order_by(Payment.submitted_at.desc())
        .all()
    )
    return payments


# ── Borrower: My Loan-Specific Payments ──────────────────────────────
@router.get(
    "/my/loans/{loan_id}/payments",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_borrower)],
)
def get_my_loan_payments(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List payment records for a specific loan owned by the borrower."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan or loan.borrower_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan not found or does not belong to you",
        )

    payments = (
        db.query(Payment)
        .filter(Payment.loan_id == loan_id, Payment.borrower_id == current_user.id)
        .order_by(Payment.submitted_at.desc())
        .all()
    )
    return payments


# ── Admin: Loan-Specific Payments ───────────────────────────────────
@router.get(
    "/loans/{loan_id}/payments",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)],
)
def get_loan_payments_admin(
    loan_id: int,
    db: Session = Depends(get_db),
):
    """List payment history for any loan. Admin only."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan not found",
        )

    payments = (
        db.query(Payment)
        .filter(Payment.loan_id == loan_id)
        .order_by(Payment.submitted_at.desc())
        .all()
    )
    return payments


# ── Shared: Get Single Payment Detail ────────────────────────────────
@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment_detail(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed payment record.
    Accessible by Admin or the Borrower who owns the payment.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Authorization
    if current_user.role != UserRole.ADMIN and payment.borrower_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment


# ── Shared: Secure Screenshot Image Streaming ────────────────────────
@router.get(
    "/payments/{payment_id}/screenshot",
    response_class=FileResponse,
)
def get_payment_screenshot(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream payment screenshot image securely.
    Admin can access any screenshot; Borrower can only access their own.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Authorization check
    if current_user.role != UserRole.ADMIN and payment.borrower_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this screenshot",
        )

    if not payment.screenshot_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No screenshot uploaded for this payment",
        )

    file_path = get_screenshot_path(payment.screenshot_url)
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "image/png"

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=f"payment_{payment.id}_proof{file_path.suffix}",
    )


# ── Admin: Record Past Payment (No Screenshot Required) ──────────────
from pydantic import BaseModel as _PydanticBase
from decimal import Decimal as _Decimal

class AdminRecordPaymentRequest(_PydanticBase):
    loan_id: int
    amount: _Decimal
    payment_month: str   # YYYY-MM
    payment_date: str    # YYYY-MM-DD
    notes: Optional[str] = None


@router.post(
    "/payments/admin-record",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Record a past/offline payment - Admin Only",
)
def admin_record_payment(
    payload: AdminRecordPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Admin-only: Record a payment that was already made (cash, UPI before KredoBook setup).
    Creates a VERIFIED payment instantly - no screenshot required.
    Loan remaining balance is updated immediately.
    """
    from app.services.loan_service import get_remaining_balance, get_total_paid
    from app.models.loan import LoanStatus
    from datetime import date as _date

    # Validate loan
    loan = db.query(Loan).filter(Loan.id == payload.loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status == LoanStatus.PAID:
        raise HTTPException(status_code=400, detail="Loan is already fully paid")
    if loan.status == LoanStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot record payment for a cancelled loan")

    # Validate amount vs remaining balance
    remaining = get_remaining_balance(db, loan)
    if payload.amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    if payload.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds remaining balance of Rs.{remaining:,.0f}"
        )

    # Parse payment date
    try:
        parsed_date = _date.fromisoformat(payload.payment_date.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment_date. Use YYYY-MM-DD format")

    note_text = payload.notes.strip() if payload.notes else "Recorded by admin"
    now = datetime.now(timezone.utc)
    norm_date = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)

    # Create VERIFIED payment directly (no screenshot)
    payment = Payment(
        loan_id=loan.id,
        borrower_id=loan.borrower_id,
        amount=payload.amount,
        payment_month=payload.payment_month.strip(),
        payment_date=norm_date,
        screenshot_url=None,
        status=PaymentStatus.VERIFIED,
        submitted_at=now,
        verified_at=now,
        verified_by=current_user.id,
        rejection_reason=note_text,
    )
    db.add(payment)

    # Auto-close loan if now fully paid
    new_paid = get_total_paid(db, loan.id) + payload.amount
    new_remaining = loan.total_payable - new_paid
    if new_remaining <= Decimal("0"):
        loan.status = LoanStatus.PAID

    db.commit()
    db.refresh(payment)
    return payment


@router.patch(
    "/payments/{payment_id}/admin-record",
    response_model=PaymentResponse,
    dependencies=[Depends(require_admin)],
    summary="Correct a past/offline payment - Admin Only",
)
def update_admin_recorded_payment(
    payment_id: int,
    payload: AdminPastPaymentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Correct a verified payment that was recorded offline by an admin."""
    from app.models.loan import LoanStatus
    from app.services.loan_service import get_total_paid

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != PaymentStatus.VERIFIED or payment.screenshot_url:
        raise HTTPException(
            status_code=400,
            detail="Only verified past/offline payments can be edited",
        )

    loan = db.query(Loan).filter(Loan.id == payment.loan_id).with_for_update().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Associated loan not found")
    if loan.status == LoanStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot edit a payment for a cancelled loan")

    try:
        parsed_date = date.fromisoformat(payload.payment_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment_date. Use YYYY-MM-DD format")

    verified_total = get_total_paid(db, loan.id)
    corrected_total = verified_total - payment.amount + payload.amount
    if corrected_total > loan.total_payable:
        raise HTTPException(
            status_code=400,
            detail=f"Corrected amount exceeds the loan balance. Maximum allowed is Rs.{loan.total_payable - (verified_total - payment.amount):,.2f}",
        )

    payment.amount = payload.amount
    payment.payment_month = payload.payment_month
    payment.payment_date = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    payment.rejection_reason = payload.notes.strip() if payload.notes and payload.notes.strip() else "Recorded by admin"
    payment.verified_by = current_user.id
    loan.status = LoanStatus.PAID if corrected_total >= loan.total_payable else LoanStatus.ACTIVE

    db.commit()
    db.refresh(payment)
    return payment
