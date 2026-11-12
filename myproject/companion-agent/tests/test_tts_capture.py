"""TTS 采集：送进合成引擎的文本、出来的音频、首包耗时、上限与打断。不依赖 LiveKit。"""

import io
import wave
from types import SimpleNamespace

import pytest

from companion.adapters.voice.tts_capture import BYTES_PER_SAMPLE, TtsCapture, pcm_to_wav


def frame(n_samples=1600, rate=16000, channels=1, byte=1):
    return SimpleNamespace(data=bytes([byte]) * (n_samples * BYTES_PER_SAMPLE * channels), sample_rate=rate, num_channels=channels)


async def agen(items):
    for i in items:
        yield i


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


async def drain(it):
    return [x async for x in it]


async def run(capture, texts, frames, *, clock=None, complete=True):
    out_text = await drain(capture.tee_text(agen(texts)))
    out_frames = await drain(capture.tee_frames(agen(frames)))
    return out_text, out_frames, capture.finish(completed=complete)


async def test_text_and_frames_pass_through_untouched_while_being_recorded():
    texts, frames = ["先歇一会儿，", "我在。"], [frame(), frame()]
    cap = TtsCapture()
    out_text, out_frames, seg = await run(cap, texts, frames)
    assert out_text == texts and out_frames == frames          # 采集不能改变放出去的内容
    assert seg.text == "先歇一会儿，我在。" and len(seg.pcm) == 2 * 1600 * BYTES_PER_SAMPLE
    assert (seg.sample_rate, seg.channels, seg.completed, seg.truncated) == (16000, 1, True, False)


async def test_audio_duration_comes_from_the_samples_not_the_wall_clock():
    seg = (await run(TtsCapture(), ["x"], [frame(n_samples=16000)]))[2]
    assert seg.audio_ms == 1000


async def test_ttfb_is_first_audio_minus_first_text():
    clock = Clock()
    cap = TtsCapture(clock=clock)
    it = cap.tee_text(agen(["你好"]))
    clock.t = 10.0
    await drain(it)
    clock.t = 10.35
    await drain(cap.tee_frames(agen([frame()])))
    assert cap.finish(completed=True).ttfb_ms == 350


async def test_no_audio_means_no_ttfb_and_empty_pcm():
    seg = (await run(TtsCapture(), ["你好"], []))[2]
    assert seg.ttfb_ms is None and seg.pcm == b"" and seg.audio_ms == 0


async def test_audio_beyond_the_cap_is_cut_and_flagged_but_still_played():
    cap = TtsCapture(max_seconds=1.0)
    frames = [frame(n_samples=16000), frame(n_samples=16000)]
    _, out_frames, seg = await run(cap, ["x"], frames)
    assert len(out_frames) == 2                                # 播放不受影响
    assert seg.truncated and seg.audio_ms == 1000


async def test_a_sample_rate_change_stops_recording_instead_of_mixing_formats():
    _, out_frames, seg = await run(TtsCapture(), ["x"], [frame(rate=16000), frame(rate=24000)])
    assert len(out_frames) == 2 and seg.truncated and seg.sample_rate == 16000 and seg.audio_ms == 100


async def test_an_interrupted_synthesis_keeps_what_was_produced_so_far():
    seg = (await run(TtsCapture(), ["先歇一会儿"], [frame()], complete=False))[2]
    assert seg.completed is False and seg.text == "先歇一会儿" and seg.pcm


async def test_started_only_after_text_arrives():
    cap = TtsCapture()
    assert not cap.started
    await drain(cap.tee_text(agen(["x"])))
    assert cap.started


def test_wav_container_is_readable_and_matches_the_pcm():
    pcm = bytes(range(256)) * 10
    with wave.open(io.BytesIO(pcm_to_wav(pcm, sample_rate=24000, channels=1))) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())) == (24000, 1, 2, pcm)
