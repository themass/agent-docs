"""WAV → STT：切帧、拼最终结果、位宽检查。用假 STT，不联网。"""

import asyncio

import pytest
from livekit import rtc
from livekit.agents import stt as lk_stt

from companion.voice.stt_transcribe import FRAME_MS, transcribe_wav, wav_frames
from companion.voice.tts_capture import pcm_to_wav


class FakeStream:
    """像真实识别器：事件在收到音频之后才出现；``script`` 里的 ("after_frames", n) 表示收到 n 帧后再继续。"""

    hang = False

    def __init__(self, texts, script=None):
        self.frames, self.ended, self.closed = [], False, False
        # 默认：音频推完之后才出结果，和真实识别器一样；不然 collect 会在帧推出去之前就结束了
        self._script = script or ([("after_end", 0)] + [("final", t) for t in texts] + ([("eos", "")] if texts else []))

    def push_frame(self, f):
        self.frames.append(f)

    def end_input(self):
        self.ended = True

    async def aclose(self):
        self.closed = True

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        yield lk_stt.SpeechEvent(type=lk_stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                 alternatives=[lk_stt.SpeechData(language="zh", text="先")])
        for kind, value in self._script:
            if kind == "after_frames":
                while len(self.frames) < value:
                    await asyncio.sleep(0.005)
            elif kind == "after_end":
                while not self.ended:
                    await asyncio.sleep(0.005)
            elif kind == "final":
                yield lk_stt.SpeechEvent(type=lk_stt.SpeechEventType.FINAL_TRANSCRIPT,
                                         alternatives=[lk_stt.SpeechData(language="zh", text=value)])
            elif kind == "eos":
                yield lk_stt.SpeechEvent(type=lk_stt.SpeechEventType.END_OF_SPEECH)
        if self.hang:           # 火山识别完就断开，插件一直重连：迭代器永远不结束
            await asyncio.sleep(3600)


class FakeStt:
    def __init__(self, texts, script=None):
        self.stream_obj, self.language = FakeStream(texts, script), None

    def stream(self, *, language):
        self.language = language
        return self.stream_obj


WAV_1S = pcm_to_wav(b"\x01\x00" * 16000, sample_rate=16000)


def test_audio_is_cut_into_100ms_frames():
    frames = list(wav_frames(WAV_1S, rtc))
    assert len(frames) == 10 and all(f.samples_per_channel == 16000 * FRAME_MS // 1000 for f in frames)


def test_a_non_16bit_wav_is_refused_instead_of_read_as_noise():
    import io, wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(b"\x00" * 800)
    with pytest.raises(ValueError):
        list(wav_frames(buf.getvalue(), rtc))


async def test_final_results_are_joined_and_interim_ones_ignored():
    stt = FakeStt(["先歇一会儿，", "我在。"])
    assert await transcribe_wav(stt, WAV_1S, pace=False) == "先歇一会儿，我在。"
    s = stt.stream_obj
    assert len(s.frames) == 10 and s.ended and s.closed and stt.language == "zh"


async def test_the_stream_is_closed_even_when_recognition_fails():
    stt = FakeStt([])

    async def boom(self):
        raise RuntimeError("asr down")
        yield
    stt.stream_obj._gen = boom.__get__(stt.stream_obj)
    with pytest.raises(RuntimeError):
        await transcribe_wav(stt, WAV_1S, pace=False)
    assert stt.stream_obj.closed


async def test_it_returns_once_the_audio_is_in_and_things_go_quiet_even_if_the_stream_never_ends():
    stt = FakeStt(["先歇一会儿，我在。"])
    stt.stream_obj.hang = True
    assert await asyncio.wait_for(transcribe_wav(stt, WAV_1S, pace=False, timeout=5, settle=0.3), 2) == "先歇一会儿，我在。"
    assert stt.stream_obj.closed


async def test_a_timeout_without_any_result_is_an_error_not_an_empty_string():
    stt = FakeStt([])
    stt.stream_obj.hang = True
    with pytest.raises(TimeoutError):
        await transcribe_wav(stt, WAV_1S, pace=False, timeout=0.2)
    assert stt.stream_obj.closed


async def test_frames_are_paced_in_real_time_by_default():
    import time

    stt = FakeStt(["好"])
    t0 = time.monotonic()
    await transcribe_wav(stt, pcm_to_wav(b"\x01\x00" * 3200, sample_rate=16000))      # 0.2 秒 = 2 帧
    assert time.monotonic() - t0 >= 0.19


async def test_an_end_of_speech_in_the_middle_of_the_audio_does_not_cut_off_the_rest():
    # 一句话中间停顿一下，识别器就可能先发一个 end_of_speech；后半句在音频推完之后才出来
    wav = pcm_to_wav(b"\x01\x00" * 6400, sample_rate=16000)           # 0.4 秒 = 4 帧
    script = [("after_frames", 2), ("final", "先歇一会儿，"), ("eos", ""),
              ("after_end", 0), ("final", "我在这儿陪着你。"), ("eos", "")]
    stt = FakeStt([], script)
    stt.stream_obj.hang = True
    assert await transcribe_wav(stt, wav, settle=0.3, timeout=5) == "先歇一会儿，我在这儿陪着你。"


async def test_a_late_final_after_the_last_end_of_speech_is_still_collected():
    script = [("after_end", 0), ("final", "第一段"), ("eos", ""), ("final", "补上的一段")]
    stt = FakeStt([], script)
    stt.stream_obj.hang = True
    assert await transcribe_wav(stt, WAV_1S, pace=False, settle=0.3, timeout=5) == "第一段补上的一段"
