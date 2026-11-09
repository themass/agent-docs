"""A mail server that never answers must not hold the request open.

Live (2026-11-08): the resend button read "发送中…" with no end. The SMTP connection had no
timeout, so a silent server blocked the request forever."""

from __future__ import annotations

import smtplib

import pytest

from jc.exceptions import AppError
from jc.services import email_service as module


@pytest.mark.asyncio
async def test_a_silent_mail_server_gets_a_timeout_and_a_clear_error(monkeypatch):
    seen: dict = {}

    class SilentSMTP:
        def __init__(self, host, port, timeout=None, **kwargs):
            seen["timeout"] = timeout
            raise TimeoutError("timed out")

    monkeypatch.setattr(module.smtplib, "SMTP", SilentSMTP)
    monkeypatch.setattr(module.settings, "jc_smtp_use_ssl", False, raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_host", "smtp.example.test", raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_user", "u", raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_password", "p", raising=False)
    service = module.EmailService()
    with pytest.raises(AppError) as info:
        await service.send_email_verification(
            to_email="u@example.test", verify_url="https://x.test/v", verification_code="1234",
        )
    assert info.value.code == "email_send_failed"
    assert seen["timeout"] == module.SMTP_TIMEOUT_SEC


@pytest.mark.asyncio
async def test_a_refused_login_is_also_reported_as_a_failed_send(monkeypatch):
    class RefusingSMTP:
        def __init__(self, host, port, timeout=None, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            pass

        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    monkeypatch.setattr(module.smtplib, "SMTP", RefusingSMTP)
    monkeypatch.setattr(module.settings, "jc_smtp_use_ssl", False, raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_host", "smtp.example.test", raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_user", "u", raising=False)
    monkeypatch.setattr(module.settings, "jc_smtp_password", "p", raising=False)
    with pytest.raises(AppError) as info:
        await module.EmailService().send_email_verification(
            to_email="u@example.test", verify_url="https://x.test/v", verification_code="1234",
        )
    assert info.value.code == "email_send_failed"
