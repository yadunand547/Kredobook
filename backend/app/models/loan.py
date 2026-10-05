"""
Loan model - represents loans given to borrowers.
"""

import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Numeric, Date, DateTime, Enum, ForeignKey, Text, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LoanStatus(str, enum.Enum):
    """Enumeration of possible loan statuses."""
    ACTIVE = "ACTIVE"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class Loan(Base):
    """
    Loan model for the loan management system.

    - loan_date: the actual date money was given to the borrower.
    - total_payable: manually entered by admin (no interest calculation).
    - A borrower can have multiple loans, each tracked separately.
    - All monetary values use NUMERIC/DECIMAL (no floats).
    """

    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    borrower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    loan_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    loan_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_payable: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    minimum_monthly_payment: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, name="loan_status", create_constraint=True),
        nullable=False,
        default=LoanStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    borrower: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="loans",
        foreign_keys=[borrower_id],
    )
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        "Payment",
        back_populates="loan",
    )

    # Additional indexes
    __table_args__ = (
        Index("ix_loans_status", "status"),
        Index("ix_loans_loan_date", "loan_date"),
    )

    def __repr__(self) -> str:
        return f"<Loan(id={self.id}, borrower_id={self.borrower_id}, amount={self.loan_amount})>"
