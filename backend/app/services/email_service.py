"""
KredoBook Email Service

Renders premium Jinja2 HTML templates and sends through Brevo's HTTPS API.
Returns a clear failure when delivery is disabled or Brevo is not configured.
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
import httpx

from app.config import settings

logger = logging.getLogger("loantracker.email")
_BREVO_SEND_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"

# Template Engine Setup
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "email" / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _fmt_currency(amount: float) -> str:
    if amount is None:
        return "\u20b90"
    try:
        return f"\u20b9{amount:,.0f}"
    except (TypeError, ValueError):
        return f"\u20b9{amount}"


def _fmt_date(d) -> str:
    if d is None:
        return "-"
    if isinstance(d, (date, datetime)):
        return d.strftime("%d %b %Y")
    return str(d)


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    to_email = (to_email or "").strip()
    if not to_email:
        return False, "Recipient email address is required"

    if not settings.EMAIL_ENABLED:
        error = "Email delivery is disabled. Set EMAIL_ENABLED=true in the deployed backend environment."
        logger.warning(error)
        return False, error

    provider = settings.EMAIL_PROVIDER.strip().lower()
    api_key = settings.BREVO_API_KEY.strip()
    sender_email = settings.EMAIL_FROM.strip()

    if provider != "brevo":
        error = "Unsupported EMAIL_PROVIDER. Set EMAIL_PROVIDER=brevo."
        logger.error(error)
        return False, error

    missing_settings = [
        name
        for name, value in {
            "BREVO_API_KEY": api_key,
            "EMAIL_FROM": sender_email,
        }.items()
        if not value
    ]
    if missing_settings:
        error = f"Email delivery is not configured. Missing: {', '.join(missing_settings)}."
        logger.error(error)
        return False, error

    try:
        payload = {
            "sender": {"email": sender_email, "name": settings.EMAIL_FROM_NAME},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": body_html,
        }
        if body_text:
            payload["textContent"] = body_text

        logger.info("Sending email through Brevo HTTPS API to %s", to_email)
        response = httpx.post(
            _BREVO_SEND_EMAIL_URL,
            headers={"api-key": api_key, "accept": "application/json"},
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()

        logger.info(f"Email sent to {to_email} (Subject: {subject})")
        return True, None

    except httpx.HTTPStatusError as e:
        err_msg = f"Brevo API error sending to {to_email}: HTTP {e.response.status_code}"
        logger.exception(err_msg)
        return False, err_msg
    except httpx.HTTPError as e:
        err_msg = f"Brevo API error sending to {to_email}: {str(e)}"
        logger.exception(err_msg)
        return False, err_msg


def _render_template(template_name: str, context: Dict[str, Any]) -> str:
    try:
        template = _jinja_env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        logger.error(f"Template render error for {template_name}: {e}")
        raise


def send_welcome_email(
    borrower_name: str,
    borrower_email: str,
    password: Optional[str] = None,
    created_date: Optional[str] = None,
    frontend_url: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    subject = "Welcome to KredoBook!"
    ctx = {
        "borrower_name": borrower_name,
        "borrower_email": borrower_email,
        "created_date": created_date or _fmt_date(date.today()),
        "frontend_url": frontend_url or settings.FRONTEND_URL,
    }
    try:
        html_body = _render_template("welcome.html", ctx)
    except Exception as e:
        return False, f"Template error: {e}"

    plain_text = (
        f"Dear {borrower_name},\n\n"
        f"Welcome to KredoBook! Your borrower account has been created.\n\n"
        f"Email: {borrower_email}\nStatus: Active\n\n"
        f"Login at: {frontend_url or settings.FRONTEND_URL}\n\n"
        f"Regards,\nKredoBook Team\nkredobook@gmail.com"
    )
    return send_email(to_email=borrower_email, subject=subject, body_html=html_body, body_text=plain_text)


def send_new_loan_email(
    borrower_name: str,
    borrower_email: str,
    loan_id: int,
    loan_amount: float,
    total_payable: float,
    minimum_monthly_payment: float,
    loan_date: str,
    notes: Optional[str] = None,
    frontend_url: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    subject = "KredoBook - New Loan Added To Your Account"
    ctx = {
        "borrower_name": borrower_name,
        "borrower_email": borrower_email,
        "loan_id": loan_id,
        "loan_amount": loan_amount,
        "total_payable": total_payable,
        "minimum_monthly_payment": minimum_monthly_payment,
        "loan_date": _fmt_date(loan_date),
        "notes": notes,
        "loan_amount_fmt": _fmt_currency(loan_amount),
        "total_payable_fmt": _fmt_currency(total_payable),
        "minimum_monthly_payment_fmt": _fmt_currency(minimum_monthly_payment),
        "frontend_url": frontend_url or settings.FRONTEND_URL,
    }
    try:
        html_body = _render_template("new_loan.html", ctx)
    except Exception as e:
        return False, f"Template error: {e}"

    plain_text = (
        f"Dear {borrower_name},\n\n"
        f"A new loan has been added to your KredoBook account.\n\n"
        f"Loan Amount: {_fmt_currency(loan_amount)}\n"
        f"Total Payable: {_fmt_currency(total_payable)}\n"
        f"Monthly Minimum: {_fmt_currency(minimum_monthly_payment)}\n"
        f"Loan Date: {_fmt_date(loan_date)}\n\n"
        f"Regards,\nKredoBook Team\nkredobook@gmail.com"
    )
    return send_email(to_email=borrower_email, subject=subject, body_html=html_body, body_text=plain_text)


def send_monthly_reminder_email(
    borrower_name: str,
    borrower_email: str,
    total_outstanding: float,
    active_loans: List[Dict[str, Any]],
    reminder_month: str,
    frontend_url: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    subject = "KredoBook - Monthly Loan Payment Reminder"
    enriched_loans = []
    for loan in active_loans:
        enriched_loans.append({
            **loan,
            "loan_amount_fmt": _fmt_currency(float(loan.get("loan_amount", 0))),
            "total_payable_fmt": _fmt_currency(float(loan.get("total_payable", 0))),
            "paid_amount_fmt": _fmt_currency(float(loan.get("paid_amount", 0))),
            "remaining_balance_fmt": _fmt_currency(float(loan.get("remaining_balance", 0))),
            "minimum_monthly_payment_fmt": _fmt_currency(float(loan.get("minimum_monthly_payment", 0))),
            "loan_date": _fmt_date(loan.get("loan_date")),
        })

    ctx = {
        "borrower_name": borrower_name,
        "borrower_email": borrower_email,
        "total_outstanding": total_outstanding,
        "total_outstanding_fmt": _fmt_currency(total_outstanding),
        "active_loans": enriched_loans,
        "reminder_month": reminder_month,
        "frontend_url": frontend_url or settings.FRONTEND_URL,
    }
    try:
        html_body = _render_template("monthly_reminder.html", ctx)
    except Exception as e:
        return False, f"Template error: {e}"

    plain_text = (
        f"Dear {borrower_name},\n\n"
        f"Monthly Reminder - {reminder_month}\n"
        f"Total Outstanding: {_fmt_currency(total_outstanding)}\n\n"
        f"Please pay before the 2nd of this month.\n\n"
        f"Regards,\nKredoBook Team"
    )
    return send_email(to_email=borrower_email, subject=subject, body_html=html_body, body_text=plain_text)
