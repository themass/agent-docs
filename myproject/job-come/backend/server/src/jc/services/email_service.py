"""Transactional email via SMTP."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from jc.config import settings
from jc.exceptions import AppError

logger = logging.getLogger(__name__)

#: A mail server that does not answer is given up on, not waited for.
SMTP_TIMEOUT_SEC = 20


class EmailService:
    def smtp_configured(self) -> bool:
        return bool(
            settings.jc_smtp_host
            and settings.jc_smtp_user
            and settings.jc_smtp_password
        )

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        subject = "JC — 重置密码"
        body = (
            f"你好，\n\n"
            f"请点击以下链接重置密码（{settings.jc_password_reset_ttl_hours} 小时内有效）：\n"
            f"{reset_url}\n\n"
            f"如非本人操作，请忽略此邮件。\n"
        )
        await self._send(to_email=to_email, subject=subject, body=body)

    async def send_email_verification(
        self,
        *,
        to_email: str,
        verify_url: str,
        verification_code: str,
    ) -> None:
        subject = "JC — 验证邮箱"
        body = (
            f"你好，\n\n"
            f"请点击以下链接验证邮箱（{settings.jc_email_verify_ttl_hours} 小时内有效）：\n"
            f"{verify_url}\n\n"
            f"或在已登录的 JC 账户设置页输入 4 位验证码：{verification_code}\n\n"
            f"如非本人操作，请忽略此邮件。\n"
        )
        await self._send(to_email=to_email, subject=subject, body=body)

    async def _send(self, *, to_email: str, subject: str, body: str) -> None:
        if not self.smtp_configured():
            raise RuntimeError("SMTP is not configured")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.jc_email_from or settings.jc_smtp_user
        message["To"] = to_email
        message.set_content(body)

        try:
            await asyncio.to_thread(self._send_sync, message)
        except (OSError, smtplib.SMTPException) as exc:
            # Without a timeout the mail server's silence held the request open (live: the
            # resend button read "发送中…" with no end). Say it failed, and why in general.
            logger.warning("verification email not sent: %s", type(exc).__name__)
            raise AppError(
                "验证邮件发送失败或超时，请稍后再试。", code="email_send_failed"
            ) from exc

    @staticmethod
    def _send_sync(message: EmailMessage) -> None:
        timeout = SMTP_TIMEOUT_SEC
        context = ssl.create_default_context()
        if settings.jc_smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.jc_smtp_host,
                settings.jc_smtp_port,
                timeout=timeout,
                context=context,
            ) as smtp:
                smtp.login(settings.jc_smtp_user, settings.jc_smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(settings.jc_smtp_host, settings.jc_smtp_port, timeout=timeout) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings.jc_smtp_user, settings.jc_smtp_password)
            smtp.send_message(message)
