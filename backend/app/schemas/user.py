"""
Pydantic schemas for User and Borrower models.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema containing shared attributes."""
    name: str = Field(..., min_length=1, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="Unique email address")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone number")


class UserOut(BaseModel):
    """Public representation of a user (excludes password hashes)."""
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    monthly_reminder_enabled: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BorrowerCreate(BaseModel):
    """Schema for Admin creating a new borrower."""
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    password: str = Field(..., min_length=6, max_length=128, description="Initial password")
    monthly_reminder_enabled: Optional[bool] = Field(True, description="Enable monthly email reminders")


class BorrowerCreateResponse(UserOut):
    """Created borrower plus the result of its welcome-email attempt."""

    email_delivery_status: Literal["SENT", "FAILED", "SKIPPED"]
    email_delivery_error: Optional[str] = None


class BorrowerUpdate(BaseModel):
    """Schema for Admin updating an existing borrower's details."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    monthly_reminder_enabled: Optional[bool] = None


class BorrowerPasswordReset(BaseModel):
    """Admin-only request to replace a borrower's password."""

    password: str = Field(..., min_length=6, max_length=128)
