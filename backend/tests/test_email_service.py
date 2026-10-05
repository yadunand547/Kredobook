"""Unit tests for KredoBook's SMTP delivery paths.

These tests never contact Gmail. They verify the exact transport and error
handling used by the application before real credentials are supplied.
"""

from unittest.mock import MagicMock

from app.config import settings
from app.services import email_service


def configure_smtp(monkeypatch, *, port=465):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_HOST", " smtp.gmail.com ")
    monkeypatch.setattr(settings, "EMAIL_PORT", port)
    monkeypatch.setattr(settings, "EMAIL_USERNAME", " kredobook@gmail.com ")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(settings, "EMAIL_FROM", " kredobook@gmail.com ")


def test_email_reports_disabled_delivery(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")

    assert success is False
    assert "disabled" in error.lower()


def test_email_reports_missing_credentials(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_USERNAME", "")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "")

    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")

    assert success is False
    assert "EMAIL_USERNAME" in error
    assert "EMAIL_PASSWORD" in error


def test_email_rejects_incomplete_gmail_app_password(monkeypatch):
    configure_smtp(monkeypatch)
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "only fifteen chr")

    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")

    assert success is False
    assert "16 characters" in error


def test_gmail_ssl_465_strips_app_password_whitespace(monkeypatch):
    configure_smtp(monkeypatch, port=465)
    server = MagicMock()
    smtp_ssl = MagicMock()
    smtp_ssl.return_value.__enter__.return_value = server
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", smtp_ssl)

    success, error = email_service.send_email(" borrower@example.com ", "Test", "<p>Test</p>")

    assert (success, error) == (True, None)
    assert smtp_ssl.call_args.args[:2] == ("smtp.gmail.com", 465)
    assert server.login.call_args.args == ("kredobook@gmail.com", "abcdefghijklmnop")
    assert server.sendmail.call_args.args[0] == "kredobook@gmail.com"
    assert server.sendmail.call_args.args[1] == ["borrower@example.com"]


def test_gmail_starttls_587_is_supported(monkeypatch):
    configure_smtp(monkeypatch, port=587)
    server = MagicMock()
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = server
    monkeypatch.setattr(email_service.smtplib, "SMTP", smtp)

    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")

    assert (success, error) == (True, None)
    assert smtp.call_args.args[:2] == ("smtp.gmail.com", 587)
    assert server.starttls.called
    assert server.login.call_args.args == ("kredobook@gmail.com", "abcdefghijklmnop")


def test_smtp_exception_returns_a_visible_failure(monkeypatch, caplog):
    configure_smtp(monkeypatch, port=465)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", MagicMock(side_effect=OSError("network blocked")))

    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")

    assert success is False
    assert "network blocked" in error
    assert "SMTP Error sending" in caplog.text


def test_all_project_email_templates_render_and_send(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://kredobook.vercel.app")
    sent = []

    def fake_send(to_email, subject, body_html, body_text=None):
        sent.append((to_email, subject, body_html, body_text))
        return True, None

    monkeypatch.setattr(email_service, "send_email", fake_send)

    assert email_service.send_welcome_email("Asha", "asha@example.com")[0]
    assert email_service.send_new_loan_email("Asha", "asha@example.com", 1, 5000, 5500, 500, "2026-10-05")[0]
    assert email_service.send_monthly_reminder_email(
        "Asha", "asha@example.com", 5000,
        [{"loan_amount": 5000, "total_payable": 5500, "paid_amount": 500, "remaining_balance": 5000,
          "minimum_monthly_payment": 500, "loan_date": "2026-10-05"}],
        "2026-10",
    )[0]

    assert len(sent) == 3
    assert all("https://kredobook.vercel.app" in html for _, _, html, _ in sent)
