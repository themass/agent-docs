"""读取 Java 登录态（D §4）。

Java 登录成功后把 `token_<base64>` 作为 Redis 键，值是 UserPo 的 JSON，TTL 24 小时。
这里只做三件事：校验键格式、读取、只保留 id 与 level。pwd / pwdHash 立即丢弃，
不进日志、异常信息或任何下游。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from companion.ports.auth import AuthUnavailable, IdentityError, parse_bearer

logger = logging.getLogger(__name__)

# Java 的 token 是 "token_" + 标准 Base64（含 + / =），见 testserverV AuthUtil.nameToToken。
# 校验的目的不是判断真伪（真伪由「Redis 里有没有这个键」决定），而是不让客户端用任意字符串探测 Redis。
_TOKEN_KEY = re.compile(r"^token_[A-Za-z0-9+/]{8,512}={0,2}$")


class RedisTokenVerifier:
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def verify(self, authorization: str | None) -> str:
        token = parse_bearer(authorization)
        if token is None:
            raise IdentityError("missing credentials")
        key = f"token_{token}" if not token.startswith("token_") else token
        if not _TOKEN_KEY.match(key):
            raise IdentityError("invalid credentials")
        try:
            raw = await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auth redis unavailable: %s", type(exc).__name__)
            raise AuthUnavailable("auth backend unavailable") from exc
        if not raw:
            raise IdentityError("invalid credentials")
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            raise IdentityError("invalid credentials") from None
        user_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(user_id, int) or user_id <= 0:
            raise IdentityError("invalid credentials")
        # pwd / pwdHash 等字段到此为止，payload 不再保留。
        return str(user_id)
