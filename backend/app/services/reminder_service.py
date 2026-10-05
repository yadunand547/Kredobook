"""
Monthly Email Reminder Service.

Handles:
- Finding eligible borrowers with active loans and outstanding balances
- Aggregating multi-loan details into a single informational reminder email
- Idempotency checks using ReminderLog to prevent duplicate monthly emails
- Explicitly informational: NEVER creates payments or modifies balances
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.loan import Loan, LoanStatus
from app.models.reminder import ReminderLog
from app.models.user import User, UserRole
from app.services.email_service import send_monthly_reminder_email
from app.services.loan_service import get_remaining_balance, get_total_paid

logger = logging.getLogger("loantracker.reminders")


def format_currency_text(val: Decimal) -> str:
    """Format decimal currency for plain text email."""
    return f"₹{val:,.2f}"


def build_reminder_email_content(
    borrower_name: str,
    active_loans_info: List[Dict],
    target_month: str,
) -> str:
    """
    Build structured plain text content summarizing all active loans for a borrower.
    """
    total_due = sum(item["remaining"] for item in active_loans_info)
    total_min_monthly = sum(item["minimum_monthly"] for item in active_loans_info)
    loans_count = len(active_loans_info)

    lines = [
        f"Dear {borrower_name},",
        "",
        f"This is your monthly loan payment reminder from KredoBook for {target_month}.",
        f"You currently have {loans_count} active loan{'s' if loans_count > 1 else ''} with an outstanding balance.",
        "",
        "=" * 50,
        "ACTIVE LOAN SUMMARY",
        "=" * 50,
    ]

    for idx, info in enumerate(active_loans_info, 1):
        lines.extend([
            f"",
            f"Loan #{info['loan_id']} (Issued: {info['loan_date']})",
            f"  - Original Loan Amount:       {format_currency_text(info['loan_amount'])}",
            f"  - Total Payable:             {format_currency_text(info['total_payable'])}",
            f"  - Verified Paid So Far:      {format_currency_text(info['paid'])}",
            f"  - Remaining Balance:         {format_currency_text(info['remaining'])}",
            f"  - Minimum Monthly Payment:   {format_currency_text(info['minimum_monthly'])}",
        ])

    lines.extend([
        "",
        "=" * 50,
        f"Total Outstanding Across Loans: {format_currency_text(total_due)}",
        f"Total Expected Monthly Minimum: {format_currency_text(total_min_monthly)}",
        "=" * 50,
        "",
        "HOW TO SUBMIT YOUR PAYMENT:",
        "1. Transfer your payment amount via UPI or Bank Transfer.",
        "2. Login to KredoBook at your application URL.",
        "3. Select the loan you are paying and click 'Make Payment'.",
        "4. Upload your transfer screenshot proof and submit.",
        "",
        "PLEASE NOTE:",
        "- This email is an informational reminder only.",
        "- No automatic deductions or payment records are created.",
        "- Your loan balance will be updated once your payment is reviewed and verified by an admin.",
        "",
        "-" * 50,
        "Regards,",
        "KredoBook Team",
        "kredobook@gmail.com",
        "",
        "This is an automated email from KredoBook.",
        "Please do not reply directly to this message.",
    ])

    return "\n".join(lines)


def send_monthly_reminders_for_all(
    db: Session,
    target_month: Optional[str] = None,
) -> Dict:
    """
    Scan all active borrowers and dispatch monthly reminders for the specified month.
    Ensures idempotency through monthly_reminder_logs.
    """
    if not target_month:
        now = datetime.now(timezone.utc)
        target_month = f"{now.year}-{now.month:02d}"

    logger.info(f"Starting monthly reminder dispatch for month: {target_month}")

    # 1. Fetch all active borrowers with reminders enabled
    borrowers = (
        db.query(User)
        .filter(
            User.role == UserRole.BORROWER,
            User.is_active == True,  # noqa: E712
            User.monthly_reminder_enabled == True,  # noqa: E712
        )
        .all()
    )

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    details = []

    for borrower in borrowers:
        # Check if reminder was already successfully dispatched this month (Idempotency)
        existing_log = (
            db.query(ReminderLog)
            .filter(
                ReminderLog.borrower_id == borrower.id,
                ReminderLog.reminder_month == target_month,
                ReminderLog.status == "SENT",
            )
            .first()
        )

        if existing_log:
            skipped_count += 1
            details.append({
                "borrower_id": borrower.id,
                "name": borrower.name,
                "email": borrower.email,
                "status": "SKIPPED",
                "reason": "Already sent for this month",
            })
            continue

        # Find active loans with remaining balance > 0
        borrower_loans = (
            db.query(Loan)
            .filter(
                Loan.borrower_id == borrower.id,
                Loan.status == LoanStatus.ACTIVE,
            )
            .all()
        )

        active_loans_info = []
        total_outstanding = Decimal("0.00")

        for loan in borrower_loans:
            remaining = get_remaining_balance(db, loan)
            if remaining > Decimal("0.00"):
                paid = get_total_paid(db, loan.id)
                active_loans_info.append({
                    "loan_id": loan.id,
                    "loan_date": str(loan.loan_date),
                    "loan_amount": float(loan.loan_amount),
                    "total_payable": float(loan.total_payable),
                    "paid_amount": float(paid),
                    "remaining_balance": float(remaining),
                    "minimum_monthly_payment": float(loan.minimum_monthly_payment),
                })
                total_outstanding += remaining

        # If no active loans with remaining balance, skip
        if not active_loans_info:
            skipped_count += 1
            details.append({
                "borrower_id": borrower.id,
                "name": borrower.name,
                "email": borrower.email,
                "status": "SKIPPED",
                "reason": "No active loans with outstanding balance",
            })
            continue

        # Build premium HTML email and send
        success, err_msg = send_monthly_reminder_email(
            borrower_name=borrower.name,
            borrower_email=borrower.email,
            total_outstanding=float(total_outstanding),
            active_loans=active_loans_info,
            reminder_month=target_month,
        )

        if success:
            sent_count += 1
            log_status = "SENT"
        else:
            failed_count += 1
            log_status = "FAILED"

        # Record or update reminder log
        log_entry = (
            db.query(ReminderLog)
            .filter(
                ReminderLog.borrower_id == borrower.id,
                ReminderLog.reminder_month == target_month,
            )
            .first()
        )

        if not log_entry:
            log_entry = ReminderLog(
                borrower_id=borrower.id,
                reminder_month=target_month,
                loans_count=len(active_loans_info),
                total_outstanding=total_outstanding,
                status=log_status,
                error_message=err_msg,
                sent_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)
        else:
            log_entry.status = log_status
            log_entry.loans_count = len(active_loans_info)
            log_entry.total_outstanding = total_outstanding
            log_entry.error_message = err_msg
            log_entry.sent_at = datetime.now(timezone.utc)

        db.commit()

        details.append({
            "borrower_id": borrower.id,
            "name": borrower.name,
            "email": borrower.email,
            "status": log_status,
            "loans_count": len(active_loans_info),
            "total_outstanding": float(total_outstanding),
            "error": err_msg,
        })

    logger.info(
        f"Monthly reminders completed for {target_month}: "
        f"Sent={sent_count}, Skipped={skipped_count}, Failed={failed_count}"
    )

    return {
        "target_month": target_month,
        "total_borrowers_evaluated": len(borrowers),
        "sent": sent_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "details": details,
    }
