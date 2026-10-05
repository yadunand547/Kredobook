"""
Payment model - represents payments made by borrowers against their loans.
"""

from app.models import Loan
from app.models import User
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    String, Numeric, DateTime, Enum, ForeignKey, Text, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaymentStatus(str, enum.Enum):
    """Enumeration of possible payment statuses."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Payment(Base):
    """
    Payment model for the loan management system.

    Tracks individual payments made by borrowers, including screenshot proof.
    Verification workflow will be implemented in Module 4.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    borrower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    payment_month: Mapped[str] = mapped_column(
        String(7),  # Format: YYYY-MM
        nullable=False,
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    screenshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", create_constraint=True),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    loan: Mapped["Loan"] = relationship(  # noqa: F821
        "Loan",
        back_populates="payments",
    )
    borrower: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="payments",
        foreign_keys=[borrower_id],
    )
    verifier: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[verified_by],
    )

    # Additional indexes
    __table_args__ = (
        Index("ix_payments_status", "status"),
        Index("ix_payments_payment_month", "payment_month"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, loan_id={self.loan_id}, amount={self.amount})>"
