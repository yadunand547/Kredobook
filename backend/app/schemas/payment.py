"""
Pydantic schemas for Payment submission, verification, and history.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentReject(BaseModel):
    """Schema for Admin rejecting a payment with reason."""
    rejection_reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Reason why the payment submission was rejected",
    )


class AdminPastPaymentUpdate(BaseModel):
    """Admin correction for a previously recorded offline payment."""
    amount: Decimal = Field(..., gt=0, max_digits=15, decimal_places=2)
    payment_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    payment_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: Optional[str] = Field(default=None, max_length=1000)


class BorrowerSummaryInPayment(BaseModel):
    """Borrower information attached to payment responses."""
    id: int
    name: str
    email: str
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LoanSummaryInPayment(BaseModel):
    """Loan information attached to payment responses."""
    id: int
    loan_amount: Decimal
    total_payable: Decimal
    minimum_monthly_payment: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    """Full payment record returned by API."""
    id: int
    loan_id: int
    borrower_id: int
    borrower: Optional[BorrowerSummaryInPayment] = None
    loan: Optional[LoanSummaryInPayment] = None
    amount: Decimal
    payment_month: str
    payment_date: datetime
    screenshot_url: Optional[str] = None
    status: PaymentStatus
    submitted_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentVerificationResponse(BaseModel):
    """Response returned when Admin approves a payment."""
    payment: PaymentResponse
    loan_id: int
    loan_status: str
    new_remaining_balance: Decimal
    message: str
