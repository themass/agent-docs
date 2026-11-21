"""Studio identity: who is acting, decided by the server, never by the browser.

Before this module the editor chose their own ``actor`` (id + role) in the request body, so anyone who
could reach the BFF could claim to be a historical reviewer. Now:

* Humans sign in with a password. Accounts live in a JSON file that is **outside the repository**
  (``POETRY_STUDIO_USERS_FILE``); passwords are stored as scrypt hashes.
* A successful login returns an HMAC-signed bearer token (``POETRY_STUDIO_SESSION_SECRET``).
* The acting identity is taken from the token. A request-body ``actor`` is only checked for
  consistency (mismatch → 403) and is otherwise ignored.
* The account file is re-read when it changes and consulted on **every** request, so deleting a user
  or changing their role takes effect immediately instead of when their token expires.
* ``EventSource`` cannot send headers, so the event stream uses a 60-second ticket bound to one run.

Standard library only (no new dependency). ``POETRY_STUDIO_AUTH=off`` keeps the old trust-the-body
behaviour for the offline demo and tests; it is reported by ``/health/ready`` and ``/auth/me`` so the UI
can show a warning. Anything other than the literal ``off`` means authentication is required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

from agent_bff.models import ROLES

log = logging.getLogger("agent_bff.auth")

USER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")
SCRYPT_PARAMS = (2**15, 8, 1)  # N, r, p; recorded inside each hash so they can be raised later
SCRYPT_MAXMEM = 2**27
SESSION_TTL_SECONDS = 8 * 3600
TICKET_TTL_SECONDS = 60
MIN_SECRET_LENGTH = 32


def auth_mode() -> str:
    """``off`` only when explicitly spelled out; any other value (or none) fails closed."""
    return "off" if os.getenv("POETRY_STUDIO_AUTH", "required").strip().lower() == "off" else "required"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ------------------------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    n, r, p = SCRYPT_PARAMS
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=SCRYPT_MAXMEM, dklen=32)
    return f"scrypt${n}${r}${p}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_b64d(salt), n=int(n), r=int(r), p=int(p), maxmem=SCRYPT_MAXMEM, dklen=32)
        return hmac.compare_digest(digest, _b64d(expected))
    except (ValueError, TypeError):
        return False


_dummy_hash: str | None = None


def dummy_hash() -> str:
    """Verified against when the user does not exist, so unknown and wrong-password cost the same."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    return _dummy_hash


# ------------------------------------------------------------------------------------ users

@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: str
    password_hash: str


@dataclass(frozen=True)
class Identity:
    id: str
    name: str
    role: str
    expires_at: int


class UserStore:
    """Reads the account file; re-reads it whenever it changes on disk."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stamp: tuple[float, int] | None = None
        self._users: dict[str, User] = {}

    @staticmethod
    def path() -> Path | None:
        raw = os.getenv("POETRY_STUDIO_USERS_FILE", "").strip()
        return Path(raw) if raw else None

    def _load(self) -> dict[str, User]:
        path = self.path()
        if path is None:
            return {}
        try:
            stat = path.stat()
        except OSError:
            self._stamp, self._users = None, {}
            return {}
        stamp = (stat.st_mtime, stat.st_size)
        if stamp == self._stamp:
            return self._users
        users: dict[str, User] = {}
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            entries = document.get("users", []) if isinstance(document, dict) else []
        except (OSError, ValueError):
            log.error("Studio users file is unreadable; no one can sign in until it is fixed")
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            uid, role, stored = str(entry.get("id", "")), entry.get("role"), str(entry.get("password_hash", ""))
            if USER_ID.fullmatch(uid) and role in ROLES and stored.startswith("scrypt$"):
                users[uid] = User(uid, str(entry.get("name") or uid)[:100], role, stored)
            else:
                log.warning("Studio users file: skipped an invalid entry (id length %d)", len(uid))
        self._stamp, self._users = stamp, users
        return users

    def get(self, user_id: str) -> User | None:
        with self._lock:
            return self._load().get(user_id)

    def count(self) -> int:
        with self._lock:
            return len(self._load())


users = UserStore()


def secret() -> bytes | None:
    """None (login unavailable) for a missing, short or placeholder secret: tokens signed with the
    published ``.env.example`` value would be forgeable by anyone who has read the repository."""
    value = os.getenv("POETRY_STUDIO_SESSION_SECRET", "")
    if len(value) < MIN_SECRET_LENGTH or value.lower().startswith("change-me"):
        return None
    return value.encode()


def configured() -> bool:
    return secret() is not None and users.count() > 0


# ------------------------------------------------------------------------------- tokens

def _sign(claims: dict[str, Any]) -> str:
    key = secret()
    if key is None:
        raise RuntimeError("POETRY_STUDIO_SESSION_SECRET is not configured")
    body = _b64e(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_b64e(hmac.new(key, body.encode(), hashlib.sha256).digest())}"


def _verify(token: str, typ: str) -> dict[str, Any] | None:
    key = secret()
    if key is None or token.count(".") != 1 or len(token) > 2048:
        return None
    body, signature = token.split(".")
    expected = _b64e(hmac.new(key, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        claims = json.loads(_b64d(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict) or claims.get("typ") != typ:
        return None
    exp = claims.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        return None
    return claims


def issue_session(user: User) -> tuple[str, int]:
    now = int(time.time())
    expires = now + SESSION_TTL_SECONDS
    return _sign({"typ": "session", "sub": user.id, "role": user.role, "iat": now, "exp": expires}), expires


def issue_ticket(identity: Identity, run_id: str) -> tuple[str, int]:
    now = int(time.time())
    expires = now + TICKET_TTL_SECONDS
    return _sign({"typ": "sse", "sub": identity.id, "role": identity.role, "run": run_id, "iat": now, "exp": expires}), expires


def _identity(claims: dict[str, Any]) -> Identity | None:
    """The token proves who signed in; the account file decides whether they still may."""
    user = users.get(str(claims.get("sub", "")))
    if user is None or user.role != claims.get("role"):
        return None
    return Identity(user.id, user.name, user.role, int(claims["exp"]))


def identity_from_session(token: str) -> Identity | None:
    claims = _verify(token, "session")
    return _identity(claims) if claims else None


def identity_from_ticket(ticket: str, run_id: str) -> Identity | None:
    claims = _verify(ticket, "sse")
    if not claims or claims.get("run") != run_id:
        return None
    return _identity(claims)


# --------------------------------------------------------------------------- rate limiting

class LoginLimiter:
    """In-process lockout: ``max_failures`` failures per key per ``window`` seconds. Not distributed.

    When the table is full it first drops entries whose window has passed, then entries that have not reached
    the lock threshold (oldest latest failure first), and touches locked entries only if nothing else is left.
    It never clears the whole table. Remaining limit: more than MAX_KEYS *locked* keys inside one window could
    still push the oldest lock out; the per-address limiter makes that impractical from a single address.
    (review item A-17)
    """

    MAX_KEYS = 10_000

    def __init__(self, max_failures: int = 5, window: int = 300) -> None:
        self.max_failures, self.window = max_failures, window
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def blocked_for(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            attempts = self._failures.get(key)
            if not attempts:
                return 0
            while attempts and now - attempts[0] > self.window:
                attempts.popleft()
            if not attempts:
                self._failures.pop(key, None)
                return 0
            return int(self.window - (now - attempts[0])) + 1 if len(attempts) >= self.max_failures else 0

    def _evict(self, now: float) -> None:
        for key in [k for k, v in self._failures.items() if not v or now - v[-1] > self.window]:
            self._failures.pop(key, None)
        excess = len(self._failures) - self.MAX_KEYS + 1
        if excess > 0:
            # Entries that have reached the lock threshold are the ones that matter, so they go last.
            # Among the rest, the one with the oldest latest failure goes first.
            def rank(k: str) -> tuple[int, float]:
                return (len(self._failures[k]) >= self.max_failures, self._failures[k][-1])

            for key in sorted(self._failures, key=rank)[:excess]:
                self._failures.pop(key, None)

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if key not in self._failures and len(self._failures) >= self.MAX_KEYS:
                self._evict(now)
            self._failures[key].append(now)

    def succeed(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


limiter = LoginLimiter()  # per (user, address): 5 / 5 min
ip_limiter = LoginLimiter(max_failures=30, window=300)  # per address: bounds a spray across many user ids


# ------------------------------------------------------------------------------ middleware

def _denied(message: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "AUTH_REQUIRED", "message": message}}, status_code=401,
        headers={"WWW-Authenticate": "Bearer"})


class AuthMiddleware:
    """Pure ASGI (BaseHTTPMiddleware mishandles long-lived SSE responses).

    Added *inside* CORS so preflight requests and the CORS headers on 401 responses still work.
    """

    def __init__(self, app: Any, *, api_prefix: str) -> None:
        self.app = app
        self.prefix = api_prefix
        self.public = {f"{api_prefix}/auth/login"}

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS" or auth_mode() == "off":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if path in self.public or path.startswith("/health/"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        header = headers.get("authorization", "")
        identity = identity_from_session(header[7:].strip()) if header[:7].lower() == "bearer " else None
        run_prefix = f"{self.prefix}/runs/"
        if identity is None and path.startswith(run_prefix) and path.endswith("/events"):
            ticket = (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("ticket") or [""])[0]
            run_id = path[len(run_prefix):-len("/events")]
            identity = identity_from_ticket(ticket, run_id) if ticket and "/" not in run_id else None
        if identity is None:
            await _denied("需要登录,或登录已过期。")(scope, receive, send)
            return
        scope.setdefault("state", {})["identity"] = identity
        await self.app(scope, receive, send)
