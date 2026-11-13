"""复合用户 id：``app:uid``（D §10.1）。"""

from __future__ import annotations

import re

APP_PATTERN = re.compile(r"^[a-z][a-z0-9]{1,31}$")


class ScopeError(ValueError):
    pass


def compose_user_id(app: str, user_id: str) -> str:
    if not APP_PATTERN.match(app):
        raise ScopeError(f"invalid app name: {app!r}")
    if not user_id or ":" in user_id:
        # 用户 id 含冒号会与分隔符混淆，直接拒绝，不做转义。
        raise ScopeError("user id must be non-empty and must not contain ':'")
    return f"{app}:{user_id}"


def split_user_id(composite: str) -> tuple[str, str]:
    app, sep, user_id = composite.partition(":")
    if not sep or not APP_PATTERN.match(app) or not user_id:
        raise ScopeError(f"not a composite user id: {composite!r}")
    return app, user_id
