"""Transactional email via SMTP."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from jc.config import settings


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

        await asyncio.to_thread(self._send_sync, message)

    @staticmethod
    def _send_sync(message: EmailMessage) -> None:
        context = ssl.create_default_context()
        if settings.jc_smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.jc_smtp_host,
                settings.jc_smtp_port,
                context=context,
            ) as smtp:
                smtp.login(settings.jc_smtp_user, settings.jc_smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(settings.jc_smtp_host, settings.jc_smtp_port) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings.jc_smtp_user, settings.jc_smtp_password)
            smtp.send_message(message)
