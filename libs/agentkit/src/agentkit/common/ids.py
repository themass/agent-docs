from __future__ import annotations
import secrets
import string
_ALPHABET = string.ascii_lowercase + string.digits

def new_id(prefix: str, *, length: int = 16) -> str:
    if not prefix.endswith("_"):
        prefix = f"{prefix}_"
    body = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    return f"{prefix}{body}"
