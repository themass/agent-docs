"""阿里云智能语音交互（NLS）TTS 适配器。

两种模式，这里用**短文本 REST**：一次 POST 一段文字，直接返回音频字节。流式 Websocket 更适合长文本，
但对话回复本来就是一句一句的，REST 更简单、失败更好定位。

两段请求，缺一不可：
1. ``CreateToken``：用 AccessKey 签名（RPC 风格），换一个有时效的 NLS token。**AccessKey 不出现在
   TTS 请求里**，只在换 token 时用一次。
2. ``/stream/v1/tts``：拿 NLS token 合成。

签名与参数拼装都是纯函数（``rpc_signature`` / ``create_token_params`` / ``tts_query``），
可以拿固定输入做单测；真正的 HTTP 在 ``client`` 上，测试传假的即可。

需要的环境变量（凭据不进仓库）::

    ALI_TTS_APP_ID               NLS 项目 appkey
    ALI_TTS_ACCESS_KEY           阿里云 AccessKey ID（只用于换 token）
    ALI_TTS_ACCESS_KEY_SECRET    阿里云 AccessKey Secret
    ALI_TTS_ENDPOINT             默认 https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts
    ALI_TTS_TOKEN_ENDPOINT       默认 https://nls-meta.cn-shanghai.aliyuncs.com
    ALI_TTS_REGION               默认 cn-shanghai
    ALI_TTS_UID                  可选，默认取 appkey
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

from companion.service.voice.port import AudioChunk, Transcript, VoiceProviderError, VoiceRef, VoiceUnavailable

DEFAULT_ENDPOINT = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts"
DEFAULT_TOKEN_ENDPOINT = "https://nls-meta.cn-shanghai.aliyuncs.com"
DEFAULT_REGION = "cn-shanghai"
DEFAULT_VOICE = "xiaoyun"
SAMPLE_RATE = 16000
# token 提前 5 分钟视为过期，避免「刚好在请求途中失效」
TOKEN_SKEW_SEC = 300


class AliyunProtocolError(VoiceProviderError):
    """返回体不是预期结构。"""


# ---- 纯函数：签名与参数 ----


def _percent(value: str) -> str:
    """RPC 签名要求的编码：quote 后再把 + * %7E 换成对应形式。"""
    return quote(str(value), safe="~")


def canonical_query(params: Mapping[str, str]) -> str:
    """按 key 字典序拼成 key=value&...，每段都按 RPC 规则编码。"""
    return "&".join(f"{_percent(k)}={_percent(params[k])}" for k in sorted(params))


def rpc_signature(*, method: str, params: Mapping[str, str], access_key_secret: str) -> str:
    """阿里云 RPC 签名（HMAC-SHA1，签名前的 StringToSign 末尾要再加一个 &）。

    用 ``sorted`` 而不是依赖调用方顺序：顺序错了签名就对不上，而这个错误在测试里
    表现为一个空的 Base64 串，很难看出原因。
    """
    string_to_sign = f"{method.upper()}&{_percent('/')}&{_percent(canonical_query(params))}"
    digest = hmac.new(f"{access_key_secret}&".encode("utf-8"), string_to_sign.encode("utf-8"),
                      hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def create_token_params(*, access_key_id: str, region: str = DEFAULT_REGION, now: float | None = None) -> dict[str, str]:
    """CreateToken 的公共参数。``Signature`` 由调用方补（它依赖 secret）。"""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))
    return {
        "AccessKeyId": access_key_id,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": region,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": uuid.uuid4().hex,
        "SignatureVersion": "1.0",
        "Timestamp": stamp,
        "Version": "2019-02-28",
    }


def signed_token_params(*, access_key_id: str, access_key_secret: str, region: str = DEFAULT_REGION,
                        now: float | None = None) -> dict[str, str]:
    params = create_token_params(access_key_id=access_key_id, region=region, now=now)
    params["Signature"] = rpc_signature(method="POST", params=params, access_key_secret=access_key_secret)
    return params


def parse_token_response(payload: Mapping[str, Any]) -> tuple[str, int]:
    """返回 (token, 过期 unix 时间)。结构不对抛 AliyunProtocolError。"""
    token = payload.get("Token") if isinstance(payload, Mapping) else None
    if not isinstance(token, Mapping):
        raise AliyunProtocolError("CreateToken 响应里没有 Token")
    value = str(token.get("Id") or "").strip()
    try:
        expires = int(token.get("ExpireTime") or 0)
    except (TypeError, ValueError) as exc:
        raise AliyunProtocolError("CreateToken 响应的 ExpireTime 不是整数") from exc
    if not value or expires <= 0:
        raise AliyunProtocolError("CreateToken 响应缺 Id 或 ExpireTime")
    return value, expires


def tts_query(*, appkey: str, token: str, text: str, voice: str = DEFAULT_VOICE, sample_rate: int = SAMPLE_RATE,
              fmt: str = "wav", volume: int = 50, speed: int = 0, pitch: int = 0,
              text_type: str = "plain", uid: str = "") -> dict[str, str]:
    """TTS 请求参数。``text_type=ssml`` 时 text 必须是 SSML，调用方负责。

    ``fmt`` 默认 wav：短文本接口在 mp3 之外的一些格式对分块播放更挑剔，wav 最稳；
    带宽不是这里的瓶颈。
    """
    return {
        "appkey": appkey,
        "token": token,
        "text": text,
        "format": fmt,
        "sample_rate": str(sample_rate),
        "voice": voice,
        "volume": str(volume),
        "speed": str(speed),
        "pitch": str(pitch),
        "text_type": text_type,
        "uid": uid or appkey,
    }


def is_error_body(content: bytes) -> str | None:
    """TTS 成功时返回音频字节；失败时返回 **JSON**（这里查得很死：以 { 开头的短包）。

    成功响应也可能以 ``RIFF``（wav）或 ``ID3``（mp3）开头，不会被误判。
    """
    head = content[:1]
    if head != b"{":
        return None
    import json

    try:
        payload = json.loads(content.decode("utf-8", "replace"))
    except ValueError:
        return None
    if not isinstance(payload, Mapping):
        return None
    message = payload.get("message") or payload.get("Message")
    return str(message) if message else "阿里 TTS 返回错误"


# ---- HTTP ----


class HttpClient(Protocol):
    async def post(self, url: str, *, data: Mapping[str, str] | None = None,
                   headers: Mapping[str, str] | None = None) -> tuple[int, bytes]:
        """``data`` 以 **JSON** 发送（阿里 NLS 的 TTS 端点只认 JSON，表单会被拒：
        ``in post data, json format illegal``）。"""
        ...

    async def post_form(self, url: str, *, data: Mapping[str, str] | None = None) -> tuple[int, bytes]:
        """以表单发送（CreateToken 的 RPC 风格要求表单）。"""
        ...


class HttpxClient:
    """默认客户端。httpx 已是项目依赖；超时收紧，避免一句合成卡住整个回合。"""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    async def post(self, url: str, *, data: Mapping[str, str] | None = None,
                   headers: Mapping[str, str] | None = None) -> tuple[int, bytes]:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=dict(data or {}), headers=dict(headers or {}))
            return response.status_code, response.content

    async def post_form(self, url: str, *, data: Mapping[str, str] | None = None) -> tuple[int, bytes]:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, data=dict(data or {}))
            return response.status_code, response.content


# ---- 配置 ----


@dataclass(frozen=True)
class AliyunConfig:
    app_id: str
    access_key_id: str
    access_key_secret: str
    endpoint: str = DEFAULT_ENDPOINT
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT
    region: str = DEFAULT_REGION
    uid: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AliyunConfig:
        import os

        source = os.environ if env is None else env

        def read(name: str, default: str = "") -> str:
            return (source.get(name) or default).strip()

        app_id = read("ALI_TTS_APP_ID")
        key = read("ALI_TTS_ACCESS_KEY")
        secret = read("ALI_TTS_ACCESS_KEY_SECRET")
        missing = [n for n, v in (("ALI_TTS_APP_ID", app_id), ("ALI_TTS_ACCESS_KEY", key),
                                  ("ALI_TTS_ACCESS_KEY_SECRET", secret)) if not v]
        if missing:
            raise VoiceUnavailable(f"阿里 TTS 凭据缺失：{' / '.join(missing)}")
        return cls(app_id=app_id, access_key_id=key, access_key_secret=secret,
                   endpoint=read("ALI_TTS_ENDPOINT", DEFAULT_ENDPOINT),
                   token_endpoint=read("ALI_TTS_TOKEN_ENDPOINT", DEFAULT_TOKEN_ENDPOINT),
                   region=read("ALI_TTS_REGION", DEFAULT_REGION), uid=read("ALI_TTS_UID"))


# ---- 供应商 ----


@dataclass
class AliyunProvider:
    """阿里云 TTS。

    ``name`` 固定为 "aliyun"：角色卡里的 ``voice_ref.provider`` 写这个。
    token 缓存在实例里，过期的提前 5 分钟换新；换失败抛 VoiceProviderError，
    由网关决定是否切备用供应商。
    """

    config: AliyunConfig
    client: HttpClient = field(default_factory=HttpxClient)
    name: str = "aliyun"
    sample_rate: int = SAMPLE_RATE
    _token: str = ""
    _token_expires: float = 0.0

    async def _ensure_token(self, now: float | None = None) -> str:
        current = time.time() if now is None else now
        if self._token and self._token_expires - TOKEN_SKEW_SEC > current:
            return self._token
        params = signed_token_params(access_key_id=self.config.access_key_id,
                                     access_key_secret=self.config.access_key_secret,
                                     region=self.config.region)
        try:
            status, body = await self.client.post_form(self.config.token_endpoint, data=params)
        except Exception as exc:  # noqa: BLE001 —— 网络故障统一成供应商错误
            raise VoiceProviderError(f"获取 NLS token 失败：{exc}", provider=self.name,
                                     direction="tts") from exc
        if status >= 400:
            raise VoiceProviderError(f"获取 NLS token 失败：HTTP {status}", provider=self.name, direction="tts")
        import json

        try:
            payload = json.loads(body.decode("utf-8", "replace"))
        except ValueError as exc:
            raise AliyunProtocolError("CreateToken 响应不是 JSON", provider=self.name,
                                      direction="tts") from exc
        value, expires = parse_token_response(payload)
        self._token, self._token_expires = value, float(expires)
        return value

    async def tts(self, text_stream: AsyncIterator[str], voice_ref: VoiceRef) -> AsyncIterator[AudioChunk]:
        token = await self._ensure_token()
        fmt = str(voice_ref.params.get("format") or "wav")
        text_type = str(voice_ref.params.get("text_type") or "plain")
        async for text in text_stream:
            if not text.strip():
                continue
            query = tts_query(appkey=self.config.app_id, token=token, text=text,
                              voice=voice_ref.voice_id or DEFAULT_VOICE, sample_rate=self.sample_rate,
                              fmt=fmt, text_type=text_type, uid=self.config.uid,
                              volume=int(voice_ref.params.get("volume", 50)),
                              speed=int(voice_ref.params.get("speed", 0)),
                              pitch=int(voice_ref.params.get("pitch", 0)))
            try:
                status, body = await self.client.post(
                    self.config.endpoint, data=query, headers={"Content-Type": "application/json"})
            except Exception as exc:  # noqa: BLE001
                raise VoiceProviderError(f"阿里 TTS 请求失败：{exc}", provider=self.name,
                                         direction="tts") from exc
            error = is_error_body(body)
            if status >= 400 or error:
                raise VoiceProviderError(error or f"阿里 TTS HTTP {status}", provider=self.name, direction="tts")
            if body:
                yield AudioChunk(data=body, sample_rate=self.sample_rate, format=fmt)

    def asr(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        """对话只需要 TTS；识别由 LiveKit 的 STT 负责。这里明确不支持，而不是假装有。"""
        raise VoiceUnavailable("阿里适配器只实现 TTS；ASR 请用 LiveKit 的 STT 插件")

    def _expire_cache(self) -> None:
        self._token, self._token_expires = "", 0.0
