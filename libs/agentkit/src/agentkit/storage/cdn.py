"""CDN signed download URLs (Volcengine / Aliyun type-A style)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class CdnConfig:
    """CDN domain for user-facing downloads."""

    domain: str  # e.g. https://files.job.sspacee.com
    sign_key: str  # CDN console URL auth key
    url_ttl_seconds: int = 900


class CdnUrlSigner:
    """
    Type-A style CDN auth: md5(key + path + timestamp) as auth_key query param.

    Volcengine CDN and Aliyun CDN both support this pattern; exact param names
    are configured to match console (default: auth_key + t).
    """

    def __init__(self, config: CdnConfig) -> None:
        domain = config.domain.rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        self._domain = domain
        self._sign_key = config.sign_key
        self._ttl = config.url_ttl_seconds

    def sign(self, object_key: str, *, ttl_seconds: int | None = None) -> str:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        path = "/" + object_key.lstrip("/")
        expire_at = int(time.time()) + ttl
        # Type-A: auth_key = md5(sign_key + path + expire_at)
        raw = f"{self._sign_key}{path}{expire_at}"
        auth_key = hashlib.md5(raw.encode("utf-8")).hexdigest()
        encoded_path = quote(path, safe="/")
        return f"{self._domain}{encoded_path}?auth_key={auth_key}&t={expire_at}"
