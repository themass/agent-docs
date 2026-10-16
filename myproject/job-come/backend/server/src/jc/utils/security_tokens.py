"""One-time token generation and hashing."""

from __future__ import annotations

import hashlib
import secrets


def generate_token(*, nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
