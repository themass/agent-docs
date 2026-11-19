"""Publish-path 探针：链式 capture 峰值、pause/resume、AudioSource 入队峰值。"""

import logging
from types import SimpleNamespace

import pytest
from livekit import rtc
from livekit.agents.voice.io import AudioOutput, AudioOutputCapabilities

from companion.api.livekit.outbound_audio_probe import (
    OutboundAudioProbe,
    attach_outbound_audio_probe,
)


def _frame(samples: list[int], *, rate: int = 24000, channels: int = 1) -> rtc.AudioFrame:
    frame = rtc.AudioFrame.create(rate, channels, len(samples))
    mv = memoryview(frame.data)
    assert mv.format == "h"
    for i, value in enumerate(samples):
        mv[i] = value
    return frame


class _Sink(AudioOutput):
    def __init__(self):
        super().__init__(
            label="fake-sink",
            capabilities=AudioOutputCapabilities(pause=True),
            sample_rate=24000,
        )
        self.frames: list[rtc.AudioFrame] = []
        self.pauses = 0
        self.resumes = 0
        self._playback_enabled = __import__("asyncio").Event()
        self._playback_enabled.set()
        self._audio_source = SimpleNamespace(capture_frame=self._source_capture)
        self.source_frames: list[rtc.AudioFrame] = []

    async def _source_capture(self, frame: rtc.AudioFrame) -> None:
        self.source_frames.append(frame)

    async def capture_frame(self, frame: rtc.AudioFrame) -> None:
        await super().capture_frame(frame)
        self.frames.append(frame)

    def flush(self) -> None:
        super().flush()

    def clear_buffer(self) -> None:
        return None

    def pause(self) -> None:
        super().pause()
        self.pauses += 1
        self._playback_enabled.clear()

    def resume(self) -> None:
        super().resume()
        self.resumes += 1
        self._playback_enabled.set()


async def test_probe_forwards_frames_and_logs_chain_peak(caplog):
    sink = _Sink()
    # AudioOutput 会把叶子包进 _AudioSinkProxy；探针必须仍透传到真实 sink。
    probe = OutboundAudioProbe(sink, summary_every=100)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.outbound_audio_probe"):
        await probe.capture_frame(_frame([16384, -100]))
        await probe.capture_frame(_frame([0, 0, 0]))
        probe.flush()
    assert len(sink.frames) == 2
    assert any("outbound audio chain first" in r.message for r in caplog.records)
    assert any("peak=0.5000" in r.message for r in caplog.records)


async def test_probe_logs_pause_and_resume(caplog):
    sink = _Sink()
    probe = OutboundAudioProbe(sink)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.outbound_audio_probe"):
        probe.pause()
        probe.resume()
    assert sink.pauses == 1 and sink.resumes == 1
    assert any("outbound audio pause" in r.message for r in caplog.records)
    assert any("outbound audio resume" in r.message for r in caplog.records)


async def test_probe_hooks_audio_source_peak(caplog):
    sink = _Sink()
    probe = OutboundAudioProbe(sink)
    # 直接打到参与者侧的 AudioSource（绕过 pause 缓冲），证明 publish 入队有能量。
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.outbound_audio_probe"):
        await sink._audio_source.capture_frame(_frame([16384]))
    assert len(sink.source_frames) == 1
    assert any("outbound audio source first" in r.message for r in caplog.records)
    assert any("peak=0.5000" in r.message and "source" in r.message for r in caplog.records)


async def test_attach_wraps_session_output_audio():
    sink = _Sink()
    changed = []

    class Output:
        def __init__(self):
            self._audio = sink

        @property
        def audio(self):
            return self._audio

        @audio.setter
        def audio(self, value):
            self._audio = value
            changed.append(type(value).__name__)

    session = SimpleNamespace(output=Output())
    probe = attach_outbound_audio_probe(session)
    assert isinstance(probe, OutboundAudioProbe)
    assert session.output.audio is probe
    assert changed == ["OutboundAudioProbe"]
    assert attach_outbound_audio_probe(session) is probe


def test_attach_skips_when_no_audio(caplog):
    session = SimpleNamespace(output=SimpleNamespace(audio=None))
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.outbound_audio_probe"):
        assert attach_outbound_audio_probe(session) is None
    assert any("skipped" in r.message for r in caplog.records)
