"""LiveKit 入场 token 的签发与校验。

只用标准库做 HS256，不引入 PyJWT：
- 只需要一种算法，标准库 hmac/hashlib 就是权威实现；
- 测试环境（/tmp/companion-venv）不必为它装额外依赖。

claims 按 LiveKit access token 的形状构造：iss=API key，sub=identity，
nbf/exp 是秒级时间戳，权限放在 ``video`` grant 里。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from companion.service.room.livekit_port import InvalidSignature, InvalidToken, LiveKitToken, MissingCredentials, TokenError, TokenExpired

USER_IDENTITY_PREFIX = "user:"
AGENT_IDENTITY_PREFIX = "agent:"


def user_identity(user_id: str) -> str:
    return f"{USER_IDENTITY_PREFIX}{user_id}"


def agent_identity(agent_id: str) -> str:
    return f"{AGENT_IDENTITY_PREFIX}{agent_id}"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise InvalidToken("token 段不是合法的 base64url") from exc


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(signing_input: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()


def encode_jwt(payload: Mapping[str, Any], secret: str) -> str:
    """签一枚 HS256 JWT。"""
    if not secret:
        raise MissingCredentials("签名密钥为空")
    header = _b64url_encode(_json_bytes({"alg": "HS256", "typ": "JWT"}))
    body = _b64url_encode(_json_bytes(payload))
    signing_input = f"{header}.{body}".encode("ascii")
    return f"{header}.{body}.{_b64url_encode(_sign(signing_input, secret))}"


def decode_jwt(
    token: str,
    secret: str,
    *,
    now: float | None = None,
    leeway: int = 0,
) -> dict[str, Any]:
    """验签并校验有效期，返回 claims。失败抛 ``InvalidToken`` 家族。

    ``now`` 可注入，测试里不必等项目过期。
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidToken("JWT 必须是三段")
    header_segment, body_segment, signature_segment = parts

    try:
        header = json.loads(_b64url_decode(header_segment))
    except json.JSONDecodeError as exc:
        raise InvalidToken("header 不是 JSON") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise InvalidToken("只接受 HS256")

    expected = _sign(f"{header_segment}.{body_segment}".encode("ascii"), secret)
    if not hmac.compare_digest(expected, _b64url_decode(signature_segment)):
        raise InvalidSignature("签名不匹配")

    try:
        claims = json.loads(_b64url_decode(body_segment))
    except json.JSONDecodeError as exc:
        raise InvalidToken("payload 不是 JSON") from exc
    if not isinstance(claims, dict):
        raise InvalidToken("payload 必须是对象")

    moment = time.time() if now is None else now
    exp = claims.get("exp")
    if exp is None:
        raise InvalidToken("缺少 exp")
    if moment > float(exp) + leeway:
        raise TokenExpired("token 已过期")
    nbf = claims.get("nbf")
    if nbf is not None and moment + leeway < float(nbf):
        raise InvalidToken("token 尚未生效")
    return claims


@dataclass(frozen=True, slots=True)
class TokenMinter:
    """按 settings 里的 LiveKit 凭据铸造 token。

    凭据缺失不在构造时报错：服务要能起来（/health 可用），
    到真正建会话时才明确拒绝，报错信息才指向缺失的环境变量。
    """

    api_key: str
    api_secret: str
    ttl_sec: int = 600

    def __post_init__(self) -> None:
        if self.ttl_sec <= 0:
            raise ValueError("ttl_sec 必须为正")

    @classmethod
    def from_settings(cls, settings: Any) -> TokenMinter:
        return cls(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ttl_sec=settings.companion_token_ttl_sec,
        )

    def user_token(
        self,
        user_id: str,
        room: str,
        *,
        name: str = "",
        now: float | None = None,
    ) -> LiveKitToken:
        """用户的 token 必须能发数据。

        陪伴页的文字不是 HTTP 发出去的，是走 LiveKit 的数据流（客户端
        ``LiveKitCompanionTransport.sendText`` 用 ``lk.chat`` topic 开一条文本流，
        服务端 RoomIO 的 ``TOPIC_CHAT`` handler 读走）。这里给 False 的话，
        数据流发布被服务端静默拒绝：界面上消息看着发出去了，服务端一个字节都收不到，
        agent 一句话不回，日志里也没有任何错误——只有客户端侧的发送失败被吞掉。
        """
        return self._mint(
            user_identity(user_id), room, name=name, can_publish_data=True, now=now
        )

    def agent_token(
        self,
        agent_id: str,
        room: str,
        *,
        name: str = "",
        now: float | None = None,
    ) -> LiveKitToken:
        """agent 同样要能发数据：它推文字回复与各项事件到房间。"""
        return self._mint(
            agent_identity(agent_id), room, name=name, can_publish_data=True, now=now
        )

    def _mint(
        self,
        identity: str,
        room: str,
        *,
        name: str,
        can_publish_data: bool,
        now: float | None,
    ) -> LiveKitToken:
        if not self.api_key or not self.api_secret:
            raise MissingCredentials(
                "LIVEKIT_API_KEY / LIVEKIT_API_SECRET 未配置，无法签发 token"
            )
        if not identity or not room:
            raise TokenError("identity 与 room 都不能为空")

        issued_at = time.time() if now is None else now
        expires_at = int(issued_at) + self.ttl_sec
        claims: dict[str, Any] = {
            "iss": self.api_key,
            "sub": identity,
            "jti": secrets.token_hex(8),
            "nbf": int(issued_at),
            "exp": expires_at,
            "video": {
                "room": room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": can_publish_data,
            },
        }
        if name:
            claims["name"] = name
        return LiveKitToken(
            token=encode_jwt(claims, self.api_secret),
            identity=identity,
            expires_at=datetime.fromtimestamp(expires_at, UTC),
        )






