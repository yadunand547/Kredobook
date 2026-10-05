"""Unit tests for KredoBook's Brevo email delivery path."""

import httpx

from app.config import settings
from app.services import email_service


def configure_brevo(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "brevo")
    monkeypatch.setattr(settings, "BREVO_API_KEY", "xkeysib-test-key")
    monkeypatch.setattr(settings, "EMAIL_FROM", "kredobook@gmail.com")
    monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "KredoBook")


def test_email_reports_disabled_delivery(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")
    assert success is False
    assert "disabled" in error.lower()


def test_email_reports_missing_brevo_key(monkeypatch):
    configure_brevo(monkeypatch)
    monkeypatch.setattr(settings, "BREVO_API_KEY", "")
    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")
    assert success is False
    assert "BREVO_API_KEY" in error


def test_email_rejects_unknown_provider(monkeypatch):
    configure_brevo(monkeypatch)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")
    assert success is False
    assert "EMAIL_PROVIDER" in error


def test_brevo_https_request_contains_html_and_text(monkeypatch):
    configure_brevo(monkeypatch)
    request_args = {}

    def fake_post(*args, **kwargs):
        request_args["args"] = args
        request_args["kwargs"] = kwargs
        return httpx.Response(201, request=httpx.Request("POST", args[0]))

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    success, error = email_service.send_email(" borrower@example.com ", "Test", "<p>Test</p>", "Test")
    assert (success, error) == (True, None)
    assert request_args["args"] == ("https://api.brevo.com/v3/smtp/email",)
    assert request_args["kwargs"]["headers"]["api-key"] == "xkeysib-test-key"
    assert request_args["kwargs"]["json"]["to"] == [{"email": "borrower@example.com"}]
    assert request_args["kwargs"]["json"]["htmlContent"] == "<p>Test</p>"
    assert request_args["kwargs"]["json"]["textContent"] == "Test"


def test_brevo_http_error_returns_visible_failure(monkeypatch):
    configure_brevo(monkeypatch)

    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", args[0])
        return httpx.Response(401, request=request)

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    success, error = email_service.send_email("borrower@example.com", "Test", "<p>Test</p>")
    assert success is False
    assert "HTTP 401" in error


def test_all_project_email_templates_render_and_send(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://kredobook.vercel.app")
    sent = []

    def fake_send(to_email, subject, body_html, body_text=None):
        sent.append((to_email, subject, body_html, body_text))
        return True, None

    monkeypatch.setattr(email_service, "send_email", fake_send)
    assert email_service.send_welcome_email("Asha", "asha@example.com")[0]
    assert email_service.send_new_loan_email("Asha", "asha@example.com", 1, 5000, 5500, 500, "2026-10-05")[0]
    assert email_service.send_monthly_reminder_email("Asha", "asha@example.com", 5000, [{"loan_amount": 5000, "total_payable": 5500, "paid_amount": 500, "remaining_balance": 5000, "minimum_monthly_payment": 500, "loan_date": "2026-10-05"}], "2026-10")[0]
    assert len(sent) == 3
    assert all("https://kredobook.vercel.app" in html for _, _, html, _ in sent)
