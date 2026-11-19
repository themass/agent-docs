"""Mode B 探针：证明上行麦帧有没有到达 ``AgentSession`` 的 audio forward。

背景（见 side-session ``remote-pcm-rca.md`` Mode B）：

- 房间有 ``RoomIO linked``，但 post-deploy 作业里**没有** ``voice turn`` /
  ``llm_node``。
- LiveKit 自己的 ``start reading stream`` 是 DEBUG，voice.log INFO 看不到；
  所以现网日志分不清是 (B1) 帧根本没进 ``push_audio``，还是 (B2) 帧到了但
  VAD 从不 START/END。

本模块在 ``session.start`` 之后把 ``session.input.audio`` 包一层（与官方
``RecorderIO.record_input`` 同形），在 INFO 打：

1. 第一帧到达（rate/ch/samples + peak）——有这一行 ⇒ 不是 B1。
2. 周期性摘要（frames / peak_max）——能量长期 ≈0 也是证据。
3. 房间 ``track_subscribed``（远端 MIC）——订阅发生了但第一帧迟迟不来 ⇒
   forward 卡在 attach/流之前。

只观测、不改帧；不碰 STT/VAD/TTS。生产重启仍需授权。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from livekit import rtc
from livekit.agents.voice.io import AudioInput

logger = logging.getLogger(__name__)

#: 摘要间隔：48000 Hz / 480 samples ≈ 10 ms/帧 → 500 帧 ≈ 5 s。
DEFAULT_SUMMARY_EVERY = 500
#: peak（|int16|/32768）过此阈值打一条「有能量」INFO，便于从静音里捞信号。
ENERGY_PEAK = 0.02


def _int16_samples(frame: Any):
    """把帧 data 读成 int16 memoryview；读不到返回 None。"""
    data = getattr(frame, "data", None)
    if data is None:
        return None
    try:
        samples = memoryview(data)
        # LiveKit AudioFrame.data 已是 format='h'；从 bytes 来时再 cast。
        if getattr(samples, "format", None) != "h":
            samples = samples.cast("h")
    except (TypeError, ValueError):
        return None
    return samples if samples else None


def frame_peak(frame: Any) -> float:
    """单帧峰值振幅，归一化到 ``[0, 1]``。空帧 / 非 int16 返回 0。"""
    samples = _int16_samples(frame)
    if samples is None:
        return 0.0
    peak = 0
    for sample in samples:
        value = sample if sample >= 0 else -sample
        if value > peak:
            peak = value
    return peak / 32768.0


def frame_nonzero(frame: Any) -> int:
    """帧里非零 int16 样本个数。静音填充帧会是 0，哪怕 ``len(data)>0``。"""
    samples = _int16_samples(frame)
    if samples is None:
        return 0
    return sum(1 for sample in samples if sample != 0)


class InboundAudioProbe(AudioInput):
    """包在 RoomIO audio input 外：透传每一帧，顺手记到达与能量。"""

    def __init__(
        self,
        source: AudioInput,
        *,
        summary_every: int = DEFAULT_SUMMARY_EVERY,
        energy_peak: float = ENERGY_PEAK,
    ) -> None:
        super().__init__(label="InboundAudioProbe", source=source)
        self._summary_every = max(1, int(summary_every))
        self._energy_peak = max(0.0, float(energy_peak))
        self._frames = 0
        self._peak_max = 0.0
        self._energy_logged = False
        self._first_logged = False

    def __aiter__(self) -> AsyncIterator[rtc.AudioFrame]:
        return self

    async def __anext__(self) -> rtc.AudioFrame:
        assert self.source is not None
        frame = await self.source.__anext__()
        self._observe(frame)
        return frame

    def _observe(self, frame: rtc.AudioFrame) -> None:
        peak = frame_peak(frame)
        self._frames += 1
        if peak > self._peak_max:
            self._peak_max = peak

        if not self._first_logged:
            self._first_logged = True
            logger.info(
                "inbound audio first frame rate=%s ch=%s samples=%s peak=%.4f",
                getattr(frame, "sample_rate", None),
                getattr(frame, "num_channels", None),
                getattr(frame, "samples_per_channel", None),
                peak,
            )

        if not self._energy_logged and peak >= self._energy_peak:
            self._energy_logged = True
            logger.info(
                "inbound audio energy seen frames=%d peak=%.4f",
                self._frames,
                peak,
            )

        if self._frames % self._summary_every == 0:
            logger.info(
                "inbound audio summary frames=%d peak_max=%.4f energy_seen=%s",
                self._frames,
                self._peak_max,
                self._energy_logged,
            )
            self._peak_max = 0.0


def attach_inbound_audio_probe(session: Any, room: Any | None = None) -> InboundAudioProbe | None:
    """在 ``session.start`` 之后调用：包住现有 audio input，并挂 track 订阅日志。

    ``session.input.audio`` 已是 RoomIO 的流时才包；未挂音频（文字模式）返回 None。
    重新赋值会触发框架的 ``_audio_changed`` → 重启 ``_forward_audio_task``，
    与官方 RecorderIO 同一路径，安全。
    """
    audio = getattr(getattr(session, "input", None), "audio", None)
    if audio is None:
        logger.info("inbound audio probe skipped: no session.input.audio")
        return None
    if isinstance(audio, InboundAudioProbe):
        return audio

    probe = InboundAudioProbe(audio)
    session.input.audio = probe
    logger.info("inbound audio probe attached source=%s", type(audio).__name__)

    if room is not None:
        _attach_track_subscribed_log(room)

    # 用户态 / 转写：有帧但永远不 speaking / 无转写 → 偏向 B2。
    on = getattr(session, "on", None)
    if callable(on):
        def _on_user_state(ev: Any) -> None:
            logger.info(
                "inbound user_state new=%s old=%s",
                getattr(ev, "new_state", None),
                getattr(ev, "old_state", None),
            )

        def _on_transcript(ev: Any) -> None:
            text = getattr(ev, "transcript", None) or getattr(ev, "transcript_alternative", None)
            logger.info(
                "inbound user_transcript final=%s text=%r",
                getattr(ev, "is_final", None),
                (text or "")[:80],
            )

        try:
            on("user_state_changed", _on_user_state)
            on("user_input_transcribed", _on_transcript)
        except Exception as exc:  # noqa: BLE001 —— 探针失败不能拖垮进房
            logger.info("inbound speech event hooks skipped: %s", exc)

    return probe


def _attach_track_subscribed_log(room: Any) -> None:
    """远端 MIC 订阅成功打 INFO；与 first-frame 对照可证 B1。"""
    on = getattr(room, "on", None)
    if not callable(on):
        return

    def _on_track_subscribed(
        track: Any,
        publication: Any,
        participant: Any,
    ) -> None:
        kind = getattr(track, "kind", None)
        source = getattr(publication, "source", None)
        # 只关心远端音频（通常 SOURCE_MICROPHONE=2）；其它轨不刷屏。
        if kind is not None and kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "inbound track_subscribed participant=%s source=%s sid=%s",
            getattr(participant, "identity", None),
            rtc.TrackSource.Name(source) if source is not None else None,
            getattr(publication, "sid", None) or getattr(track, "sid", None),
        )

    try:
        on("track_subscribed", _on_track_subscribed)
    except Exception as exc:  # noqa: BLE001
        logger.info("inbound track_subscribed hook skipped: %s", exc)
