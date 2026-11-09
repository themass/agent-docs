"""LiveKit 入场凭证的端口：错误类型、凭证数据、签发接口。

签名实现在 adapters/livekit/tokens.py；产品与接口层只依赖这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class TokenError(Exception):
    """token 不能用于建连。"""


class InvalidToken(TokenError):
    """结构不对，或还没生效。"""


class InvalidSignature(InvalidToken):
    """签名对不上：密钥不同，或内容被改过。"""


class TokenExpired(InvalidToken):
    """已过期。"""


class MissingCredentials(TokenError):
    """没配 LiveKit 的 key/secret。"""


class LiveKitToken:
    token: str
    identity: str
    expires_at: datetime


class TokenIssuer(Protocol):
    def user_token(self, user_id: str, room: str, *, now: float | None = None) -> LiveKitToken: ...
