"""Mode B 探针：帧峰值、透传、挂到 session.input.audio。"""

from types import SimpleNamespace

import pytest
from livekit import rtc
from livekit.agents.voice.io import AudioInput

from companion.api.livekit.inbound_audio_probe import (
    InboundAudioProbe,
    attach_inbound_audio_probe,
    frame_peak,
)


def _frame(samples: list[int], *, rate: int = 48000, channels: int = 1) -> rtc.AudioFrame:
    frame = rtc.AudioFrame.create(rate, channels, len(samples))
    mv = memoryview(frame.data)
    assert mv.format == "h"
    for i, value in enumerate(samples):
        mv[i] = value
    return frame


def test_frame_peak_is_normalized_abs_max():
    assert frame_peak(_frame([0, 0, 0])) == 0.0
    assert frame_peak(_frame([16384, -100])) == pytest.approx(0.5)
    assert frame_peak(_frame([-32768])) == pytest.approx(1.0)


class _Source(AudioInput):
    def __init__(self, frames: list[rtc.AudioFrame]):
        super().__init__(label="fake")
        self._frames = list(frames)
        self.attached = 0
        self.detached = 0

    async def __anext__(self) -> rtc.AudioFrame:
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)

    def on_attached(self) -> None:
        self.attached += 1

    def on_detached(self) -> None:
        self.detached += 1


async def test_probe_forwards_frames_and_logs_first(caplog):
    import logging

    source = _Source([_frame([100, -200, 50]), _frame([0, 0])])
    probe = InboundAudioProbe(source, summary_every=100)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.inbound_audio_probe"):
        out = [frame async for frame in probe]
    assert len(out) == 2
    assert out[0].samples_per_channel == 3
    assert any("inbound audio first frame" in r.message for r in caplog.records)
    assert probe._frames == 2


async def test_attach_wraps_session_input_audio():
    source = _Source([_frame([1])])
    changed = []

    class Input:
        def __init__(self):
            self._audio = source

        @property
        def audio(self):
            return self._audio

        @audio.setter
        def audio(self, value):
            if self._audio is not None:
                self._audio.on_detached()
            self._audio = value
            changed.append(type(value).__name__)
            if value is not None:
                value.on_attached()

    session = SimpleNamespace(input=Input(), on=lambda *_a, **_k: None)
    probe = attach_inbound_audio_probe(session, room=None)
    assert isinstance(probe, InboundAudioProbe)
    assert session.input.audio is probe
    assert changed == ["InboundAudioProbe"]
    # 再挂一次是幂等的。
    assert attach_inbound_audio_probe(session, room=None) is probe


def test_attach_skips_when_no_audio(caplog):
    import logging

    session = SimpleNamespace(input=SimpleNamespace(audio=None))
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.inbound_audio_probe"):
        assert attach_inbound_audio_probe(session) is None
    assert any("skipped" in r.message for r in caplog.records)
