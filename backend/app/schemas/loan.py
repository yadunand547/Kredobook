"""
Pydantic schemas for Loan management.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.loan import LoanStatus


class LoanCreate(BaseModel):
    """Schema for Admin creating a new loan."""
    borrower_id: int = Field(..., description="ID of the borrower receiving the loan")
    loan_amount: Decimal = Field(..., gt=0, decimal_places=2, description="Actual amount given")
    loan_date: date = Field(..., description="Date money was actually given")
    total_payable: Decimal = Field(..., gt=0, decimal_places=2, description="Total amount to be repaid")
    minimum_monthly_payment: Decimal = Field(..., gt=0, decimal_places=2, description="Minimum expected monthly")
    notes: Optional[str] = Field(None, max_length=2000, description="Optional admin notes")


class LoanUpdate(BaseModel):
    """Schema for Admin updating an existing loan."""
    loan_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    loan_date: Optional[date] = None
    total_payable: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    minimum_monthly_payment: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[LoanStatus] = None


class BorrowerSummary(BaseModel):
    """Minimal borrower info embedded in loan responses."""
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class LoanResponse(BaseModel):
    """Full loan details returned by the API."""
    id: int
    borrower_id: int
    borrower: BorrowerSummary
    loan_amount: Decimal
    loan_date: date
    total_payable: Decimal
    minimum_monthly_payment: Decimal
    total_paid: Decimal
    remaining_balance: Decimal
    status: LoanStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoanSummary(BaseModel):
    """Compact loan summary for list views."""
    id: int
    borrower_id: int
    borrower: BorrowerSummary
    loan_amount: Decimal
    loan_date: date
    total_payable: Decimal
    total_paid: Decimal
    remaining_balance: Decimal
    minimum_monthly_payment: Decimal
    status: LoanStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BorrowerLoanResponse(BaseModel):
    """Loan details visible to a borrower (excludes internal info)."""
    id: int
    loan_amount: Decimal
    loan_date: date
    total_payable: Decimal
    minimum_monthly_payment: Decimal
    total_paid: Decimal
    remaining_balance: Decimal
    status: LoanStatus
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminDashboardStats(BaseModel):
    """Summary statistics for the admin dashboard."""
    total_borrowers: int
    active_loans: int
    total_amount_lent: Decimal
    total_outstanding: Decimal


class BorrowerDashboardStats(BaseModel):
    """Summary statistics for a borrower's dashboard."""
    active_loans: int
    total_outstanding: Decimal
