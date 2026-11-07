"""火山引擎语音适配器。

真实接口是二进制 websocket 流：4 字节头 + 可选序号/错误码 + 4 字节长度 + 负载。
这里把**协议编码**与**套接字**分开：帧的构造、鉴权头、响应解析都是纯函数，可以
拿固定字节做单测；真正的 socket 只在 ``client`` 上调，测试传假的即可。

需要的环境变量（一个都不能写进代码或配置文件）::

    VOLC_TTS_APP_ID        应用 ID
    VOLC_TTS_ACCESS_TOKEN  access token，鉴权头用
    VOLC_TTS_ENDPOINT      wss 地址，随集群部署变化，必须显式给
    VOLC_TTS_CLUSTER       集群名，默认 volcano_tts
    VOLC_ASR_APP_ID        可选，缺省复用 TTS 的 app id
    VOLC_ASR_ACCESS_TOKEN  可选，缺省复用 TTS 的 token
    VOLC_ASR_ENDPOINT      wss 地址；给了才启用 ASR
    VOLC_ASR_CLUSTER       默认 volcano_asr

测试环境常见做法是全部不设，``from_env()`` 抛 ``VoiceUnavailable``，网关不认识
这个供应商就不会被调用——不设凭据绝不发请求。
"""

from __future__ import annotations

import json
import os
import struct
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from companion.voice.port import (
    DEFAULT_FORMAT,
    DEFAULT_SAMPLE_RATE,
    AudioChunk,
    Transcript,
    VoiceProviderError,
    VoiceRef,
    VoiceUnavailable,
)

# 协议版本占高 4 位。火山 v1 二进制协议是 1；头长按 4 字节为单位计。
PROTOCOL_VERSION_V1 = 0b0001
HEADER_SIZE_WORDS = 1

# 消息类型
MSG_FULL_CLIENT_REQUEST = 0b0001
MSG_FULL_SERVER_RESPONSE = 0b1001
MSG_AUDIO_SERVER_RESPONSE = 0b1011
MSG_ERROR = 0b1111

# 消息类型标志位（服务端）
FLAG_NO_SEQUENCE = 0b0000
FLAG_POSITIVE_SEQUENCE = 0b0001
FLAG_LAST_NO_SEQUENCE = 0b0010
FLAG_LAST_NEGATIVE_SEQUENCE = 0b0011

# 序列化 / 压缩
SER_RAW = 0b0000
SER_JSON = 0b0001
COMP_NONE = 0b0000
COMP_GZIP = 0b0001

_HEADER_LEN = 4
_U32 = struct.Struct(">I")


class VolcengineProtocolError(VoiceProviderError):
    """帧格式不对、字段缺失。单独一类，便于和网络故障区分。"""


# ---- 帧编码（纯函数） ----


def build_header(
    message_type: int,
    flags: int = FLAG_NO_SEQUENCE,
    *,
    serialization: int = SER_JSON,
    compression: int = COMP_NONE,
) -> bytes:
    """4 字节头。四个字段各占一字节，互不干扰。"""
    if not 0 <= message_type <= 0b1111:
        raise ValueError("message_type must fit 4 bits")
    if not 0 <= flags <= 0b1111:
        raise ValueError("flags must fit 4 bits")
    return bytes(
        (
            (PROTOCOL_VERSION_V1 << 4) | HEADER_SIZE_WORDS,
            (message_type << 4) | flags,
            (serialization << 4) | compression,
            0x00,
        )
    )


def build_frame(
    message_type: int,
    payload: bytes = b"",
    *,
    flags: int = FLAG_NO_SEQUENCE,
    sequence: int | None = None,
    error_code: int | None = None,
    serialization: int = SER_JSON,
    compression: int = COMP_NONE,
) -> bytes:
    """按协议头 + 可选字段 + 长度 + 负载的顺序拼一帧。

    可选字段的顺序是协议定的：序号在有序列标志时才有，错误码只在错误帧里有。
    调用方给错组合直接报错，不猜。
    """
    out = bytearray(build_header(message_type, flags, serialization=serialization, compression=compression))
    if flags & FLAG_POSITIVE_SEQUENCE:
        if sequence is None:
            raise ValueError("sequence flag set but no sequence given")
        out += _U32.pack(sequence & 0xFFFFFFFF)
    elif sequence is not None:
        raise ValueError("sequence given without the sequence flag; server would misparse the frame")
    if message_type == MSG_ERROR:
        if error_code is None:
            raise ValueError("error frame requires an error code")
        out += _U32.pack(error_code & 0xFFFFFFFF)
    elif error_code is not None:
        raise ValueError("error_code is only valid on error frames")
    out += _U32.pack(len(payload))
    out += payload
    return bytes(out)


def build_tts_payload(
    text: str,
    voice_ref: VoiceRef,
    *,
    app_id: str,
    cluster: str,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    encoding: str = DEFAULT_FORMAT,
    operation: str = "submit",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """TTS 请求体。

    ``params`` 里的角色参数直接铺进 ``audio`` 段：语速、情绪这类是供应商维度的，
    端口层不解释；客户端传什么就传什么，多余字段由服务端忽略。
    """
    audio: dict[str, Any] = {
        "voice_type": voice_ref.voice_id,
        "encoding": encoding,
        "sample_rate": sample_rate,
        "speed_ratio": 1.0,
    }
    for key, value in voice_ref.params.items():
        if isinstance(key, str) and value is not None:
            audio[key] = value
    payload: dict[str, Any] = {
        "app": {"appid": app_id, "cluster": cluster},
        "user": {"uid": "companion"},
        "audio": audio,
        "request": {"reqid": "", "text": text, "text_type": "plain", "operation": operation},
    }
    if extra:
        for key, value in extra.items():
            payload.setdefault(key, value)
    return payload


def build_tts_frame(
    text: str,
    voice_ref: VoiceRef,
    *,
    app_id: str,
    cluster: str,
    **kwargs: Any,
) -> bytes:
    """整条 TTS 请求帧（JSON 负载、不压缩）。"""
    payload = build_tts_payload(text, voice_ref, app_id=app_id, cluster=cluster, **kwargs)
    return build_frame(
        MSG_FULL_CLIENT_REQUEST,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        serialization=SER_JSON,
    )


def build_auth_headers(access_token: str) -> dict[str, str]:
    """鉴权头。

    火山的分号是协议的一部分（``Bearer;`` 后面直接跟 token），不是笔误；写成
    标准的 ``Bearer <token>`` 会被拒。
    """
    token = access_token.strip()
    if not token:
        raise VoiceUnavailable("VOLC_TTS_ACCESS_TOKEN 为空，无法构造鉴权头")
    return {"Authorization": f"Bearer; {token}"}


@dataclass(frozen=True)
class ServerFrame:
    """解析后的一帧服务端响应。"""

    message_type: int
    flags: int
    serialization: int
    compression: int
    payload: bytes
    sequence: int | None = None
    error_code: int | None = None

    @property
    def is_last(self) -> bool:
        return self.flags in (FLAG_LAST_NO_SEQUENCE, FLAG_LAST_NEGATIVE_SEQUENCE)

    @property
    def is_audio(self) -> bool:
        return self.message_type == MSG_AUDIO_SERVER_RESPONSE

    @property
    def is_error(self) -> bool:
        return self.message_type == MSG_ERROR

    def json_payload(self) -> dict[str, Any]:
        if self.serialization != SER_JSON:
            raise VolcengineProtocolError("payload is not JSON", provider="volcengine")
        try:
            decoded = json.loads(self.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VolcengineProtocolError(
                f"payload is not valid JSON: {exc}", provider="volcengine"
            ) from exc
        if not isinstance(decoded, dict):
            raise VolcengineProtocolError("payload JSON is not an object", provider="volcengine")
        return decoded


def parse_frame(frame: bytes) -> ServerFrame:
    """切一帧。任意截断都算协议错误，不做尽力而为的猜测。

    解压不在这里做：压缩标志原样带出，由调用方决定，这样纯函数不引入 gzip 依赖
    路径之外的副作用。
    """
    if len(frame) < _HEADER_LEN + 4:
        raise VolcengineProtocolError(
            f"frame too short: {len(frame)} bytes", provider="volcengine"
        )
    header_size = (frame[0] & 0x0F) * 4
    if header_size != _HEADER_LEN:
        raise VolcengineProtocolError(
            f"unsupported header size: {header_size} bytes", provider="volcengine"
        )
    message_type = (frame[1] >> 4) & 0x0F
    flags = frame[1] & 0x0F
    serialization = (frame[2] >> 4) & 0x0F
    compression = frame[2] & 0x0F

    offset = header_size
    sequence: int | None = None
    error_code: int | None = None

    if flags & FLAG_POSITIVE_SEQUENCE:
        if len(frame) < offset + 4:
            raise VolcengineProtocolError("truncated sequence", provider="volcengine")
        (sequence,) = _U32.unpack_from(frame, offset)
        offset += 4
    if message_type == MSG_ERROR:
        if len(frame) < offset + 4:
            raise VolcengineProtocolError("truncated error code", provider="volcengine")
        (error_code,) = _U32.unpack_from(frame, offset)
        offset += 4
    if len(frame) < offset + 4:
        raise VolcengineProtocolError("truncated payload length", provider="volcengine")
    (payload_size,) = _U32.unpack_from(frame, offset)
    offset += 4
    if len(frame) < offset + payload_size:
        raise VolcengineProtocolError(
            f"payload truncated: want {payload_size}, have {len(frame) - offset}",
            provider="volcengine",
        )
    return ServerFrame(
        message_type=message_type,
        flags=flags,
        serialization=serialization,
        compression=compression,
        payload=frame[offset : offset + payload_size],
        sequence=sequence,
        error_code=error_code,
    )


def frame_format(server_frame: ServerFrame) -> str:
    """响应帧里的音频编码。

    服务端在最后一帧的 JSON 里报 ``encoding``；音频帧本身不带。网关缓存音频时
    需要这个值，取不到就用端口默认。
    """
    if not server_frame.serialization == SER_JSON:
        return DEFAULT_FORMAT
    try:
        data = server_frame.json_payload()
    except VolcengineProtocolError:
        return DEFAULT_FORMAT
    return str(data.get("encoding") or DEFAULT_FORMAT)


def parse_tts_response(server_frame: ServerFrame) -> tuple[bytes, bool]:
    """把一个响应帧拆成 (音频字节, 是否结束)。

    错误帧抛 ``VoiceProviderError``，消息里带上服务端错误码；调用方据此计失败数。
    鉴权失败重复三次也是一样的错，网关会切备用供应商——这是设计第 13 节的期望。
    """
    if server_frame.is_error:
        code = server_frame.error_code or 0
        detail = server_frame.payload.decode("utf-8", "replace")
        raise VoiceProviderError(
            f"volcengine tts error {code}: {detail}", provider="volcengine", direction="tts"
        )
    if server_frame.is_audio:
        return server_frame.payload, server_frame.is_last
    if server_frame.serialization == SER_JSON:
        # 非音频的 JSON 帧是控制信息（首帧带 reqid 等），没有音频可吐。
        return b"", server_frame.is_last
    return server_frame.payload, server_frame.is_last


def parse_asr_response(server_frame: ServerFrame) -> Transcript:
    """ASR 结果帧 → Transcript。

    中间结果 ``is_final=False``，定稿帧由服务端在 flags 上标出来。
    """
    if server_frame.is_error:
        code = server_frame.error_code or 0
        raise VoiceProviderError(
            f"volcengine asr error {code}", provider="volcengine", direction="asr"
        )
    data = server_frame.json_payload()
    result = data.get("result")
    if isinstance(result, list):
        first = result[0] if result else {}
        text = str(first.get("text") or "") if isinstance(first, Mapping) else ""
    elif isinstance(result, Mapping):
        text = str(result.get("text") or "")
    else:
        text = str(data.get("text") or "")
    confidence = data.get("confidence")
    return Transcript(
        text=text,
        is_final=bool(data.get("is_final")) or server_frame.is_last,
        confidence=float(confidence) if isinstance(confidence, (int, float)) else 0.0,
    )


# ---- 套接字（可注入） ----


@runtime_checkable
class VoiceSocket(Protocol):
    """一条已连上的语音 websocket。只要求三件事，方便测试传假的。"""

    async def send(self, data: bytes) -> None: ...

    async def recv(self) -> bytes: ...

    async def close(self) -> None: ...


class SocketConnector(Protocol):
    def connect(self, url: str, headers: Mapping[str, str]) -> Any: ...


class WebSocketConnector:
    """默认连接器：首次使用时才 import websockets（不是硬依赖）。"""

    async def connect(self, url: str, headers: Mapping[str, str]) -> VoiceSocket:
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - 走不到真实网络的环境
            raise VoiceUnavailable(
                "websockets 未安装：pip install 'websockets>=13'"
            ) from exc
        ws = await websockets.connect(
            url,
            additional_headers=dict(headers),
            max_size=None,
            ping_interval=20,
        )
        return _WebSocketAdapter(ws)


class _WebSocketAdapter:
    """把 websockets 的连接包成 VoiceSocket；只管收发与关闭。"""

    def __init__(self, ws: Any) -> None:
        self._ws = ws

    async def send(self, data: bytes) -> None:
        await self._ws.send(data)

    async def recv(self) -> bytes:
        message = await self._ws.recv()
        if isinstance(message, str):
            return message.encode("utf-8")
        return bytes(message)

    async def close(self) -> None:
        await self._ws.close()


# ---- 配置 ----


@dataclass(frozen=True)
class VolcengineConfig:
    """凭据。只从环境变量来，不从构造参数以外的地方读；构造参数由 ``from_env`` 填。"""

    app_id: str
    access_token: str
    tts_endpoint: str
    tts_cluster: str = "volcano_tts"
    asr_app_id: str = ""
    asr_access_token: str = ""
    asr_endpoint: str = ""
    asr_cluster: str = "volcano_asr"

    def __post_init__(self) -> None:
        """ASR 凭据缺省继承 TTS。

        放在这里而不是只放在 ``from_env``：直接构造配置的调用方（脚本、测试）不该
        被迫重复填同一对凭据，而漏填的后果是运行时鉴权失败，比一处默认值难查得多。
        """
        if not self.asr_app_id:
            object.__setattr__(self, "asr_app_id", self.app_id)
        if not self.asr_access_token:
            object.__setattr__(self, "asr_access_token", self.access_token)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> VolcengineConfig:
        source = os.environ if env is None else env

        def read(name: str, default: str = "") -> str:
            return (source.get(name) or default).strip()

        app_id = read("VOLC_TTS_APP_ID")
        token = read("VOLC_TTS_ACCESS_TOKEN")
        endpoint = read("VOLC_TTS_ENDPOINT")
        missing = [
            name
            for name, value in (
                ("VOLC_TTS_APP_ID", app_id),
                ("VOLC_TTS_ACCESS_TOKEN", token),
                ("VOLC_TTS_ENDPOINT", endpoint),
            )
            if not value
        ]
        if missing:
            raise VoiceUnavailable(
                "火山引擎 TTS 配置缺失：" + ", ".join(missing)
            )
        return cls(
            app_id=app_id,
            access_token=token,
            tts_endpoint=endpoint,
            tts_cluster=read("VOLC_TTS_CLUSTER", "volcano_tts"),
            asr_app_id=read("VOLC_ASR_APP_ID") or app_id,
            asr_access_token=read("VOLC_ASR_ACCESS_TOKEN") or token,
            asr_endpoint=read("VOLC_ASR_ENDPOINT"),
            asr_cluster=read("VOLC_ASR_CLUSTER", "volcano_asr"),
        )


# ---- 供应商 ----


@dataclass
class VolcengineProvider:
    """火山引擎实现。

    ``client`` 是连接器，测试传假的不碰网络。``name`` 固定为 "volcengine"：角色卡
    里的 ``voice_ref.provider`` 就写这个。
    """

    config: VolcengineConfig
    client: SocketConnector = field(default_factory=WebSocketConnector)
    name: str = "volcengine"
    sample_rate: int = DEFAULT_SAMPLE_RATE
    encoding: str = DEFAULT_FORMAT

    def _audio_format(self, voice_ref: VoiceRef) -> str:
        return str(voice_ref.params.get("encoding") or self.encoding)

    async def tts(
        self, text_stream: AsyncIterator[str], voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]:
        headers = build_auth_headers(self.config.access_token)
        socket = await self.client.connect(self.config.tts_endpoint, headers)
        try:
            async for text in text_stream:
                if not text.strip():
                    continue
                frame = build_tts_frame(
                    text,
                    voice_ref,
                    app_id=self.config.app_id,
                    cluster=self.config.tts_cluster,
                    sample_rate=self.sample_rate,
                    encoding=self._audio_format(voice_ref),
                )
                await socket.send(frame)
                async for chunk in self._read_tts(socket, voice_ref):
                    yield chunk
        finally:
            await socket.close()

    async def _read_tts(
        self, socket: VoiceSocket, voice_ref: VoiceRef
    ) -> AsyncIterator[AudioChunk]:
        """读到这一句的最后一帧为止。

        一句一个请求、一个结束帧：不让两句话的序号混在一条流里，断句的边界就是
        缓冲的边界。
        """
        fmt = self._audio_format(voice_ref)
        while True:
            raw = await socket.recv()
            server_frame = parse_frame(raw)
            audio, done = parse_tts_response(server_frame)
            if audio:
                yield AudioChunk(data=audio, sample_rate=self.sample_rate, format=fmt)
            if done:
                return

    async def asr(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        if not self.config.asr_endpoint:
            raise VoiceUnavailable("VOLC_ASR_ENDPOINT 未配置，火山 ASR 不可用")
        headers = build_auth_headers(self.config.asr_access_token)
        socket = await self.client.connect(self.config.asr_endpoint, headers)
        try:
            # ASR 的二进制帧格式与 TTS 不同；这里只发裸音频、按 JSON 帧收结果，
            # 接真实服务前要按 v2 音频帧格式替换这一段的编码（见模块 docstring）。
            async for audio in audio_stream:
                if audio:
                    await socket.send(audio)
            while True:
                raw = await socket.recv()
                server_frame = parse_frame(raw)
                transcript = parse_asr_response(server_frame)
                yield transcript
                if transcript.is_final and server_frame.is_last:
                    return
        finally:
            await socket.close()
