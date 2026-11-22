"""剧本房 RTC 适配：Protocol + Memory（单测）+ LiveKit（真房推流）。

所有 ``livekit`` import 只允许出现在本模块。生产 agent 入口不得 import 本文件。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# livekit 仅本文件可见；其它 script_room / 生产入口禁止依赖。
from livekit import rtc

from companion.api.livekit.topics import TEXT_TOPIC

logger = logging.getLogger(__name__)

_DEFAULT_CHANNELS = 1

#: 剧本房读写的文本流 topic。生产上陪伴页的文字就是从这条 topic 进来的，
#: 剧本房要模拟的是同一条通道，所以**必须**与生产同一个值——取 ``api.livekit.topics``
#: 那一份，而不是在这里再写一个字面量：值写两份的话，生产改名而这里不跟，
#: 剧本房就会往一条没人听的 topic 上发文字，表现是「发了、服务端当没看见」。
#: （不 import ``entrypoint``：它在模块级 import 音频探针，会把 livekit.agents 拖进来。）
_TEXT_STREAM_TOPIC = TEXT_TOPIC

#: 入向 data 包处理器：``(payload, topic, publisher_identity, publisher_kind)``。
#: ``publisher_kind`` 为大写名（``STANDARD`` / ``AGENT`` …），与 ``ProtocolBridge`` 的身份白名单口径一致。
DataHandler = Callable[[bytes, str, str, str], Awaitable[None]]

#: 入向 ``lk.chat`` 文本流处理器：``(reader, participant_identity)``。
#: 形状照 LiveKit 的 ``Room.register_text_stream_handler``——**同步**回调，
#: ``reader`` 是 ``TextStreamReader``（异步迭代 / ``read_all``）。要读它得起 task。
TextHandler = Callable[[Any, str], None]


def _kind_name(kind: Any) -> str:
    """``Participant.kind`` 是 protobuf 整型枚举；归一成 ``STANDARD`` / ``AGENT`` 等大写名。"""
    if isinstance(kind, int) and not isinstance(kind, bool):
        try:
            kind = rtc.ParticipantKind.Name(kind)
        except ValueError:
            return str(kind)
    name = getattr(kind, "name", None)
    text = name if isinstance(name, str) else str(kind)
    text = text.rsplit(".", 1)[-1].upper()
    return text.removeprefix("PARTICIPANT_KIND_")


@runtime_checkable
class RtcAdapter(Protocol):
    def set_data_handler(self, handler: DataHandler | None) -> None: ...

    def set_text_handler(self, handler: TextHandler | None) -> None:
        """订阅一条 ``lk.chat`` 文本流。real_turn 模式的用户文字走这里。"""
        ...

    async def connect(self, url: str, token: str) -> None: ...

    async def publish_data(self, topic: str, payload: bytes) -> None: ...

    async def send_text(self, topic: str, text: str) -> None:
        """发一条文本流（``lk.chat``）。real_turn 模式下用户 participant 用它发文字。"""
        ...

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None: ...

    async def wait_for_remote_participant(self, *, timeout: float) -> None: ...

    async def close(self) -> None: ...


@dataclass
class MemoryRtcAdapter:
    """单测用：按序记录 publish_data / publish_pcm / send_text；simulate_* 唤醒与喂入向。"""

    published: list[tuple] = field(default_factory=list)
    _remote: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _connected: bool = field(default=False, repr=False)
    _data_handler: DataHandler | None = field(default=None, repr=False)
    _text_handler: TextHandler | None = field(default=None, repr=False)

    def set_data_handler(self, handler: DataHandler | None) -> None:
        self._data_handler = handler

    def set_text_handler(self, handler: TextHandler | None) -> None:
        self._text_handler = handler

    async def simulate_text(self, text: str, *, participant_identity: str = "phone-1") -> None:
        """测试：模拟对端在 ``lk.chat`` 上发来的这条文本流（同步回调 + reader 两条形状都吃）。"""
        handler = self._text_handler
        if handler is None:
            return
        handler(_MemoryTextReader(text), participant_identity)

    async def simulate_data(
        self,
        payload: bytes,
        *,
        topic: str,
        publisher_identity: str,
        publisher_kind: str = "STANDARD",
    ) -> None:
        """测试：模拟真房 ``data_received``，经 ``set_data_handler`` 注册的处理器送达。"""
        handler = self._data_handler
        if handler is None:
            return
        await handler(payload, topic, publisher_identity, publisher_kind)

    async def connect(self, url: str, token: str) -> None:
        del url, token
        self._connected = True
        self._remote.clear()

    async def publish_data(self, topic: str, payload: bytes) -> None:
        self.published.append(("data", topic, payload))

    async def send_text(self, topic: str, text: str) -> None:
        self.published.append(("text", topic, text))

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None:
        self.published.append(("pcm", frame, sample_rate))

    def simulate_remote_join(self) -> None:
        self._remote.set()

    async def wait_for_remote_participant(self, *, timeout: float) -> None:
        await asyncio.wait_for(self._remote.wait(), timeout=timeout)

    async def close(self) -> None:
        self._connected = False
        self._remote.clear()


class _MemoryTextReader:
    """``TextStreamReader`` 的替身：只提供 real_turn 用到的那两个形状。

    真实 reader 是异步迭代器并有 ``read_all()``；替身照这两个写，多一个都没有——
    真接口改了这里会红，正是我们想要的耦合方向。
    """

    def __init__(self, text: str) -> None:
        self._text = text

    def __aiter__(self):
        return self._one_shot()

    async def _one_shot(self):
        if self._text:
            yield self._text

    async def read_all(self) -> str:
        return self._text


class LiveKitRtcAdapter:
    """经 LiveKit Room 连接 / local_participant 发 data + PCM 音轨。

    PCM：首次 ``publish_pcm``（或已 connect）时建 AudioSource + LocalAudioTrack 并 publish；
    之后 ``capture_frame``。``sample_rate`` 由调用方传入（Volcengine 默认可后接）。
    """

    def __init__(self) -> None:
        self._room: rtc.Room | None = None
        self._remote = asyncio.Event()
        self._audio_source: rtc.AudioSource | None = None
        self._audio_sample_rate: int | None = None
        self._track_published = False
        self._data_handler: DataHandler | None = None
        self._data_tasks: set[asyncio.Task[None]] = set()
        self._text_handler: TextHandler | None = None
        self._text_topic: str | None = None

    def set_data_handler(self, handler: DataHandler | None) -> None:
        self._data_handler = handler

    def set_text_handler(self, handler: TextHandler | None) -> None:
        """订阅 ``lk.chat`` 文本流。

        **connect 前后都能调**，两种时机都按「handler 已挂上」对外表现：
        ``connect`` 之前调用只是记下，由 :meth:`connect` 在建好 Room 之后补登记
        （剧本房 ``real_turn`` 就是这么用的——它要保证「客户端进房之前 handler 全挂好」，
        而 Room 那一刻还不存在）；``connect`` 之后调用则立即在当前 Room 上登记。

        重复注册同一 topic 时 LiveKit 会 raise，所以这里先退订再订——让「换个 handler」
        这种用法可用，而不是逼调用方去记 SDK 的这个坑。传 ``None`` 退订。
        """
        self._text_handler = handler
        room = self._room
        if room is None:
            return
        self._detach_text_handler(room)
        if handler is None:
            return
        room.register_text_stream_handler(_TEXT_STREAM_TOPIC, handler)
        self._text_topic = _TEXT_STREAM_TOPIC

    def _detach_text_handler(self, room: rtc.Room) -> None:
        topic = self._text_topic
        self._text_topic = None
        if topic is not None:
            room.unregister_text_stream_handler(topic)

    def _dispatch_data(self, packet: Any) -> None:
        """``data_received`` 是同步回调：起 task 跑 async handler，字段映射同 ``protocol_bridge.attach``。"""
        handler = self._data_handler
        if handler is None:
            return
        publisher = getattr(packet, "participant", None)
        coro = handler(
            getattr(packet, "data", b"") or b"",
            getattr(packet, "topic", None) or "",
            getattr(publisher, "identity", None) or "",
            _kind_name(getattr(publisher, "kind", None)),
        )
        task = asyncio.get_running_loop().create_task(coro)
        self._data_tasks.add(task)
        task.add_done_callback(self._on_data_task_done)

    def _on_data_task_done(self, task: asyncio.Task[None]) -> None:
        self._data_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.warning("script room data handler failed: %s", task.exception())

    async def connect(self, url: str, token: str) -> None:
        room = rtc.Room()
        self._remote.clear()

        @room.on("data_received")
        def _on_data_received(packet: Any) -> None:
            self._dispatch_data(packet)

        @room.on("participant_connected")
        def _on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            del participant
            self._remote.set()

        await room.connect(url, token)
        self._room = room
        # connect 之前挂上的文本 handler 在这里补登记（Room 是这一刻才存在的）。
        # 接线顺序与生产同构：entrypoint 也是「先挂好 handler，再让客户端进来」。
        if self._text_handler is not None:
            room.register_text_stream_handler(_TEXT_STREAM_TOPIC, self._text_handler)
            self._text_topic = _TEXT_STREAM_TOPIC
        # 已在房内的远端（CLI / 手机先入）
        if room.remote_participants:
            self._remote.set()

    async def publish_data(self, topic: str, payload: bytes) -> None:
        room = self._require_room()
        await room.local_participant.publish_data(payload, topic=topic)

    async def send_text(self, topic: str, text: str) -> None:
        room = self._require_room()
        await room.local_participant.send_text(text, topic=topic)

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None:
        room = self._require_room()
        await self._ensure_audio_track(sample_rate)
        assert self._audio_source is not None
        # LiveKit AudioFrame 要 int16 对齐；fake TTS 用 utf-8 种子，尾块可能奇数长。
        usable = len(frame) - (len(frame) % (2 * _DEFAULT_CHANNELS))
        if usable <= 0:
            return
        if usable != len(frame):
            frame = frame[:usable]
        samples_per_channel = usable // 2 // _DEFAULT_CHANNELS
        audio_frame = rtc.AudioFrame(
            data=frame,
            sample_rate=sample_rate,
            num_channels=_DEFAULT_CHANNELS,
            samples_per_channel=samples_per_channel,
        )
        await self._audio_source.capture_frame(audio_frame)

    async def wait_for_remote_participant(self, *, timeout: float) -> None:
        await asyncio.wait_for(self._remote.wait(), timeout=timeout)

    async def close(self) -> None:
        room = self._room
        self._room = None
        for task in list(self._data_tasks):
            task.cancel()
        self._data_tasks.clear()
        self._audio_source = None
        self._audio_sample_rate = None
        self._track_published = False
        self._remote.clear()
        if room is not None:
            self._detach_text_handler(room)
            try:
                await room.disconnect()
            except Exception:  # noqa: BLE001 — 关闭路径不抛
                logger.warning("LiveKitRtcAdapter disconnect failed", exc_info=True)

    def _require_room(self) -> rtc.Room:
        if self._room is None:
            raise RuntimeError("LiveKitRtcAdapter not connected")
        return self._room

    async def _ensure_audio_track(self, sample_rate: int) -> None:
        if self._track_published and self._audio_source is not None:
            if self._audio_sample_rate != sample_rate:
                raise ValueError(
                    f"sample_rate changed from {self._audio_sample_rate} to {sample_rate}"
                )
            return
        room = self._require_room()
        source = rtc.AudioSource(sample_rate, _DEFAULT_CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("script-pcm", source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await room.local_participant.publish_track(track, options)
        self._audio_source = source
        self._audio_sample_rate = sample_rate
        self._track_published = True
