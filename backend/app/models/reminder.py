"""
Reminder Log model - tracks monthly email reminders sent to borrowers.
Ensures idempotency (at most one reminder per borrower per month).
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    String, Numeric, DateTime, ForeignKey, Integer, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReminderLog(Base):
    """
    Tracks monthly reminder dispatches for auditing and idempotency.
    """

    __tablename__ = "monthly_reminder_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    borrower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_month: Mapped[str] = mapped_column(
        String(7),  # Format: YYYY-MM
        nullable=False,
        index=True,
    )
    loans_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),  # SENT, SKIPPED, FAILED
        nullable=False,
        default="SENT",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    borrower: Mapped["User"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[borrower_id],
    )

    # Idempotency constraint: a borrower gets at most 1 reminder log per month
    __table_args__ = (
        UniqueConstraint("borrower_id", "reminder_month", name="uq_borrower_month_reminder"),
        Index("ix_reminders_month_status", "reminder_month", "status"),
    )

    def __repr__(self) -> str:
        return f"<ReminderLog(id={self.id}, borrower_id={self.borrower_id}, month='{self.reminder_month}', status='{self.status}')>"
