"""Publish-path 探针：TTS 出帧之后、远端 sink 之前卡在哪一层。

背景（见 side-session ``remote-pcm-rca.md``）：

- ``tts done peak≈0.9`` 已证合成侧有能量。
- 客户端 ``remote_pcm_summary maxLevel=0`` 持续全零。
- RoomIO 默认 ``resume_false_interruption=True``：用户一开口就 ``audio_output.pause()``，
  帧会进 ``_audio_buf`` 但 ``_forward_audio`` 在 ``_playback_enabled`` 清掉时
  **不**调用 ``AudioSource.capture_frame``——端上只能听到 AudioSource 空队列的静音填充。

本模块在 ``session.start`` 之后包住 ``session.output.audio``（与 inbound 探针对称），INFO 打：

1. **chain** —— ``capture_frame`` 进入 RoomIO/Recorder/Synchronizer 链（合成→发布链已接通）
2. **pause/resume** —— 假打断是否把播放门闩拉上
3. **source** —— 真正 ``AudioSource.capture_frame`` 入队的峰值（有这一行且 peak>0 仍远端 0
   ⇒ 断点在 WebRTC 发布/订阅/端上；chain 有、source 无 ⇒ 断在 pause/forward 丢帧）

只观测；不改帧。生产重启仍需授权。
"""

from __future__ import annotations

import logging
from typing import Any

from livekit import rtc
from livekit.agents.voice.io import AudioOutput, AudioOutputCapabilities

from companion.api.livekit.inbound_audio_probe import ENERGY_PEAK, frame_peak

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_EVERY = 500


def _unwrap_participant_output(node: AudioOutput | None) -> AudioOutput | None:
    """沿 ``next_in_chain`` 找到带 ``_audio_source`` 的 RoomIO 输出（或测试替身）。"""
    seen: set[int] = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if hasattr(node, "_audio_source"):
            return node
        node = getattr(node, "next_in_chain", None)
    return None


class OutboundAudioProbe(AudioOutput):
    """包在 RoomIO/Recorder 音频输出外：透传帧，记 chain / source / pause。"""

    def __init__(
        self,
        sink: AudioOutput,
        *,
        summary_every: int = DEFAULT_SUMMARY_EVERY,
        energy_peak: float = ENERGY_PEAK,
    ) -> None:
        caps = getattr(sink, "capabilities", None) or AudioOutputCapabilities(pause=True)
        # 保持 pause 能力，假打断路径才能把 pause 传到真正的 RoomIO 输出。
        if not getattr(caps, "pause", False):
            caps = AudioOutputCapabilities(pause=True)
        super().__init__(
            label="OutboundAudioProbe",
            next_in_chain=sink,
            sample_rate=sink.sample_rate,
            capabilities=caps,
        )
        self._summary_every = max(1, int(summary_every))
        self._energy_peak = max(0.0, float(energy_peak))
        self._chain_frames = 0
        self._chain_peak_max = 0.0
        self._chain_energy_logged = False
        self._chain_first_logged = False
        self._source_frames = 0
        self._source_peak_max = 0.0
        self._source_energy_logged = False
        self._source_first_logged = False
        self._source_hooked = False
        self._hook_audio_source()

    def _hook_audio_source(self) -> None:
        """在 ``AudioSource.capture_frame`` 上挂观测：pause 丢帧时这里不会亮。"""
        if self._source_hooked:
            return
        participant = _unwrap_participant_output(self.next_in_chain)
        source = getattr(participant, "_audio_source", None) if participant is not None else None
        capture = getattr(source, "capture_frame", None)
        if source is None or capture is None or not callable(capture):
            logger.info("outbound audio source hook skipped: no AudioSource on chain")
            return

        probe = self
        original = capture

        async def _watched(frame: rtc.AudioFrame, *args: Any, **kwargs: Any):
            probe._observe_source(frame)
            return await original(frame, *args, **kwargs)

        try:
            source.capture_frame = _watched  # type: ignore[method-assign]
        except Exception as exc:  # noqa: BLE001 —— 探针失败不能拖垮发布
            logger.info("outbound audio source hook failed: %s", exc)
            return
        self._source_hooked = True
        logger.info(
            "outbound audio source hook attached sink=%s",
            type(participant).__name__,
        )

    async def capture_frame(self, frame: rtc.AudioFrame) -> None:
        self._observe_chain(frame)
        assert self.next_in_chain is not None
        await self.next_in_chain.capture_frame(frame)
        await super().capture_frame(frame)

    def flush(self) -> None:
        if self.next_in_chain:
            self.next_in_chain.flush()
        super().flush()

    def clear_buffer(self) -> None:
        if self.next_in_chain:
            self.next_in_chain.clear_buffer()

    def pause(self) -> None:
        logger.info("outbound audio pause")
        super().pause()

    def resume(self) -> None:
        logger.info("outbound audio resume")
        super().resume()

    def _observe_chain(self, frame: rtc.AudioFrame) -> None:
        peak = frame_peak(frame)
        self._chain_frames += 1
        if peak > self._chain_peak_max:
            self._chain_peak_max = peak

        if not self._chain_first_logged:
            self._chain_first_logged = True
            logger.info(
                "outbound audio chain first rate=%s ch=%s samples=%s peak=%.4f",
                getattr(frame, "sample_rate", None),
                getattr(frame, "num_channels", None),
                getattr(frame, "samples_per_channel", None),
                peak,
            )

        if not self._chain_energy_logged and peak >= self._energy_peak:
            self._chain_energy_logged = True
            logger.info(
                "outbound audio chain energy seen frames=%d peak=%.4f",
                self._chain_frames,
                peak,
            )

        if self._chain_frames % self._summary_every == 0:
            logger.info(
                "outbound audio chain summary frames=%d peak_max=%.4f energy_seen=%s",
                self._chain_frames,
                self._chain_peak_max,
                self._chain_energy_logged,
            )
            self._chain_peak_max = 0.0

    def _observe_source(self, frame: rtc.AudioFrame) -> None:
        peak = frame_peak(frame)
        self._source_frames += 1
        if peak > self._source_peak_max:
            self._source_peak_max = peak

        if not self._source_first_logged:
            self._source_first_logged = True
            logger.info(
                "outbound audio source first rate=%s ch=%s samples=%s peak=%.4f",
                getattr(frame, "sample_rate", None),
                getattr(frame, "num_channels", None),
                getattr(frame, "samples_per_channel", None),
                peak,
            )

        if not self._source_energy_logged and peak >= self._energy_peak:
            self._source_energy_logged = True
            logger.info(
                "outbound audio source energy seen frames=%d peak=%.4f",
                self._source_frames,
                peak,
            )

        if self._source_frames % self._summary_every == 0:
            logger.info(
                "outbound audio source summary frames=%d peak_max=%.4f energy_seen=%s",
                self._source_frames,
                self._source_peak_max,
                self._source_energy_logged,
            )
            self._source_peak_max = 0.0


def attach_outbound_audio_probe(session: Any) -> OutboundAudioProbe | None:
    """在 ``session.start`` 之后调用：包住现有 audio output（含 Recorder/Synchronizer）。

    ``session.output.audio`` 已是 RoomIO 链时才包；文字模式返回 None。
    重新赋值会 ``on_detached``/``on_attached``，与官方 RecorderIO 同一路径。
    """
    audio = getattr(getattr(session, "output", None), "audio", None)
    if audio is None:
        logger.info("outbound audio probe skipped: no session.output.audio")
        return None
    if isinstance(audio, OutboundAudioProbe):
        return audio

    probe = OutboundAudioProbe(audio)
    session.output.audio = probe
    logger.info("outbound audio probe attached sink=%s", type(audio).__name__)
    return probe
