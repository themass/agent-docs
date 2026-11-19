"""剧本房 RTC 适配：Protocol + Memory（单测）+ LiveKit（真房推流）。

所有 ``livekit`` import 只允许出现在本模块。生产 agent 入口不得 import 本文件。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# livekit 仅本文件可见；其它 script_room / 生产入口禁止依赖。
from livekit import rtc

logger = logging.getLogger(__name__)

_DEFAULT_CHANNELS = 1


@runtime_checkable
class RtcAdapter(Protocol):
    async def connect(self, url: str, token: str) -> None: ...

    async def publish_data(self, topic: str, payload: bytes) -> None: ...

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None: ...

    async def wait_for_remote_participant(self, *, timeout: float) -> None: ...

    async def close(self) -> None: ...


@dataclass
class MemoryRtcAdapter:
    """单测用：按序记录 publish_data / publish_pcm；simulate_remote_join 唤醒等待。"""

    published: list[tuple] = field(default_factory=list)
    _remote: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _connected: bool = field(default=False, repr=False)

    async def connect(self, url: str, token: str) -> None:
        del url, token
        self._connected = True
        self._remote.clear()

    async def publish_data(self, topic: str, payload: bytes) -> None:
        self.published.append(("data", topic, payload))

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None:
        self.published.append(("pcm", frame, sample_rate))

    def simulate_remote_join(self) -> None:
        self._remote.set()

    async def wait_for_remote_participant(self, *, timeout: float) -> None:
        await asyncio.wait_for(self._remote.wait(), timeout=timeout)

    async def close(self) -> None:
        self._connected = False
        self._remote.clear()


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

    async def connect(self, url: str, token: str) -> None:
        room = rtc.Room()
        self._remote.clear()

        @room.on("participant_connected")
        def _on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            del participant
            self._remote.set()

        await room.connect(url, token)
        self._room = room
        # 已在房内的远端（CLI / 手机先入）
        if room.remote_participants:
            self._remote.set()

    async def publish_data(self, topic: str, payload: bytes) -> None:
        room = self._require_room()
        await room.local_participant.publish_data(payload, topic=topic)

    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None:
        room = self._require_room()
        await self._ensure_audio_track(sample_rate)
        assert self._audio_source is not None
        samples_per_channel = len(frame) // 2 // _DEFAULT_CHANNELS
        if samples_per_channel <= 0:
            return
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
        self._audio_source = None
        self._audio_sample_rate = None
        self._track_published = False
        self._remote.clear()
        if room is not None:
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
