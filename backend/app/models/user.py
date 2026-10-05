"""
User model - represents system users (ADMIN and BORROWER roles).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """Enumeration of user roles in the system."""
    ADMIN = "ADMIN"
    BORROWER = "BORROWER"


class User(Base):
    """
    User model for the loan management system.

    Represents both admins who manage loans and borrowers who receive them.
    Authentication logic will be implemented in Module 2.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.BORROWER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monthly_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    loans: Mapped[list["Loan"]] = relationship(  # noqa: F821
        "Loan",
        back_populates="borrower",
        foreign_keys="[Loan.borrower_id]",
    )
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        "Payment",
        back_populates="borrower",
        foreign_keys="[Payment.borrower_id]",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.value}')>"
