"""HttpOnly cookie helpers."""

from __future__ import annotations

from fastapi import Response

from jobcome.config import settings

GUEST_COOKIE = "jc_guest"
SESSION_COOKIE = "jc_session"


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "httponly": True,
        "secure": settings.job_come_cookie_secure,
        "samesite": "lax",
        "max_age": max_age,
        "path": "/",
    }


def set_guest_cookie(response: Response, guest_session_id: str) -> None:
    response.set_cookie(
        GUEST_COOKIE,
        guest_session_id,
        **_cookie_kwargs(settings.job_come_guest_ttl_days * 86400),
    )


def clear_guest_cookie(response: Response) -> None:
    response.delete_cookie(GUEST_COOKIE, path="/")


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        **_cookie_kwargs(settings.job_come_session_ttl_days * 86400),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
