"""身份验证端口：凭据解析与错误类型。实现在 adapters/auth/。"""

from __future__ import annotations

from typing import Protocol


class IdentityError(Exception):
    """凭据缺失或无效 -> 401。"""


class AuthUnavailable(RuntimeError):
    """认证依赖（如 Redis）不可用 -> 503。不能当作 401：那会让用户以为要重新登录。"""


def parse_bearer(authorization: str | None) -> str | None:
    """取 ``Bearer <token>`` 里的 token；不是 Bearer 形式就当没给。"""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    value = value.strip()
    return value or None


class CredentialVerifier(Protocol):
    async def verify(self, authorization: str | None) -> str:
        """返回已核实的 user_id；无效抛 IdentityError，依赖不可用抛 AuthUnavailable。"""
        ...
