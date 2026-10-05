"""
Monthly Email Reminder API routes.

- Admin endpoint: Trigger/simulate monthly reminder dispatch
- Admin endpoint: View reminder audit logs
- Shared endpoint: Toggle reminder setting for a borrower
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.reminder import ReminderLog
from app.models.user import User, UserRole
from app.services.reminder_service import send_monthly_reminders_for_all

router = APIRouter(tags=["Monthly Reminders"])


class ReminderToggleRequest(BaseModel):
    enabled: bool


class ReminderLogResponse(BaseModel):
    id: int
    borrower_id: int
    reminder_month: str
    loans_count: int
    total_outstanding: float
    status: str
    error_message: Optional[str] = None
    sent_at: str

    model_config = ConfigDict(from_attributes=True)


# ── Admin: Trigger Monthly Reminders ─────────────────────────────────
@router.post(
    "/reminders/send-monthly",
    dependencies=[Depends(require_admin)],
)
def trigger_monthly_reminders(
    month: Optional[str] = Query(None, description="Target month in YYYY-MM format (defaults to current month)"),
    db: Session = Depends(get_db),
):
    """
    Trigger the monthly email reminder dispatch job.
    Admin-only endpoint. Scans eligible active borrowers with outstanding balances.
    """
    result = send_monthly_reminders_for_all(db=db, target_month=month)
    return result


# ── Admin: View Reminder Audit Logs ──────────────────────────────────
@router.get(
    "/reminders/logs",
    dependencies=[Depends(require_admin)],
)
def list_reminder_logs(
    month: Optional[str] = Query(None, description="Filter by YYYY-MM"),
    db: Session = Depends(get_db),
):
    """
    List historical monthly reminder logs. Admin only.
    """
    query = db.query(ReminderLog)
    if month:
        query = query.filter(ReminderLog.reminder_month == month)

    logs = query.order_by(ReminderLog.sent_at.desc()).limit(100).all()

    return [
        {
            "id": log.id,
            "borrower_id": log.borrower_id,
            "borrower_name": log.borrower.name if log.borrower else f"Borrower #{log.borrower_id}",
            "borrower_email": log.borrower.email if log.borrower else "",
            "reminder_month": log.reminder_month,
            "loans_count": log.loans_count,
            "total_outstanding": float(log.total_outstanding),
            "status": log.status,
            "error_message": log.error_message,
            "sent_at": log.sent_at.isoformat(),
        }
        for log in logs
    ]


# ── Toggle Reminder Preferences ──────────────────────────────────────
@router.patch(
    "/borrowers/{borrower_id}/reminders",
)
def toggle_reminder_setting(
    borrower_id: int,
    payload: ReminderToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Toggle monthly email reminder preference.
    Accessible by Admin or the Borrower themselves.
    """
    borrower = db.query(User).filter(User.id == borrower_id, User.role == UserRole.BORROWER).first()
    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found",
        )

    # Authorization
    if current_user.role != UserRole.ADMIN and current_user.id != borrower.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this setting",
        )

    borrower.monthly_reminder_enabled = payload.enabled
    db.commit()
    db.refresh(borrower)

    return {
        "borrower_id": borrower.id,
        "monthly_reminder_enabled": borrower.monthly_reminder_enabled,
        "message": f"Monthly email reminders {'enabled' if borrower.monthly_reminder_enabled else 'disabled'}.",
    }


# ── Test Email Endpoint (Admin Only) ──────────────────────────────────
@router.post(
    "/reminders/test-email",
    dependencies=[Depends(require_admin)],
)
def test_email_dispatch(
    to_email: str = Query(..., description="Recipient email address to test"),
):
    """
    Send a test email using the configured Brevo email service.
    Admin-only endpoint for verifying email credentials.
    """
    from app.services.email_service import send_email

    subject = "KredoBook - Test Email Notification"
    body_html = """
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px;background:#F0F4FF;">
      <div style="background:linear-gradient(135deg,#1E40AF,#2563EB);padding:28px;border-radius:12px 12px 0 0;text-align:center;">
        <span style="font-size:22px;font-weight:800;color:#fff;">Kredo</span><span style="font-size:22px;font-weight:800;color:#93C5FD;">Book</span>
      </div>
      <div style="background:#fff;padding:32px;border-radius:0 0 12px 12px;">
        <h2 style="color:#1E3A8A;">&#10003; Test Email Successful</h2>
        <p style="color:#374151;">Your KredoBook Brevo email configuration is working correctly.</p>
        <p style="color:#6B7280;font-size:13px;">This is an automated test from KredoBook. Please do not reply.</p>
      </div>
    </div>
    """

    success, error_msg = send_email(to_email=to_email, subject=subject, body_html=body_html)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {error_msg}",
        )

    return {
        "success": True,
        "to": to_email,
        "message": "Test email sent successfully via KredoBook mail service.",
    }


# ── Scheduler Status Endpoint (Admin Only) ─────────────────────────
@router.get(
    "/reminders/scheduler-status",
    dependencies=[Depends(require_admin)],
)
def scheduler_status():
    """
    Returns the current scheduler status and the next scheduled run time.
    Admin-only endpoint.
    """
    from app.scheduler import get_scheduler_status
    return get_scheduler_status()
