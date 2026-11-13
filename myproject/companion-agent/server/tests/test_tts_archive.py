"""归档器：同意之前不留音频、分段累积成一个回合一段音频、上传失败不假装有音频。"""

import io
import wave

from sqlalchemy import select

from companion.adapters.store.sql.qa import SqlQaStore
from companion.adapters.store.sql.schema import voice_turn
from companion.voice.tts_archive import MAX_OPEN_TURNS, TtsArchiver
from companion.voice.tts_capture import TtsSegment


def seg(text="先歇一会儿。", pcm=b"\x01\x00" * 16000, rate=16000, completed=True, ttfb=300, truncated=False):
    return TtsSegment(text=text, pcm=pcm, sample_rate=rate, channels=1, ttfb_ms=ttfb, truncated=truncated, completed=completed)


class Objects:
    def __init__(self, fail=False):
        self.put_calls, self.fail = [], fail

    async def put(self, *, key, data, content_type):
        if self.fail:
            raise RuntimeError("tos down")
        self.put_calls.append((key, data, content_type))


class Compliance:
    def __init__(self, allowed):
        self.allowed = allowed

    async def qa_content_allowed(self, *, owner_id):
        return self.allowed


def archiver(engine, *, allowed=True, objects=None):
    objects = Objects() if objects is None else objects
    return TtsArchiver(qa=SqlQaStore(engine), compliance=Compliance(allowed), objects=objects, key_prefix="p/",
                       provider="volcengine", voice="saturn"), objects


async def call(a, turn="T1", segment=None, owner=1002):
    await a(turn_id=turn, session_id=7, owner_id=owner, role_id="linche", user_message_id=11, segment=segment or seg())


async def rows(engine):
    async with engine.connect() as conn:
        return (await conn.execute(select(voice_turn))).mappings().all()


async def test_with_consent_text_and_audio_are_stored_under_a_per_turn_key(sqlite_engine):
    a, objects = archiver(sqlite_engine)
    await call(a)
    (key, data, ctype), = objects.put_calls
    assert key == "p/qa/tts/1002/7/T1.wav" and ctype == "audio/wav"
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 16000 and w.getnframes() == 16000
    (r,) = await rows(sqlite_engine)
    assert (r["tts_text"], r["audio_out_key"], r["tts_ttfb_ms"], r["tts_audio_ms"]) == (["先歇一会儿。"], key, 300, 1000)
    assert (r["tts_provider"], r["tts_voice"], r["content_kept"]) == ("volcengine", "saturn", True)


async def test_without_consent_nothing_is_uploaded_and_no_text_or_audio_key_is_stored(sqlite_engine):
    a, objects = archiver(sqlite_engine, allowed=False)
    await call(a)
    assert objects.put_calls == []
    (r,) = await rows(sqlite_engine)
    assert r["tts_text"] is None and r["audio_out_key"] is None and not r["content_kept"]
    assert (r["tts_ttfb_ms"], r["tts_audio_ms"], r["tts_voice"]) == (300, 1000, "saturn")   # 指标仍在


async def test_segments_of_one_turn_accumulate_into_one_audio_file(sqlite_engine):
    a, objects = archiver(sqlite_engine)
    await call(a, segment=seg("第一句。", pcm=b"\x01\x00" * 16000))
    await call(a, segment=seg("第二句。", pcm=b"\x02\x00" * 8000, ttfb=999))
    (r,) = await rows(sqlite_engine)
    assert r["tts_text"] == ["第一句。", "第二句。"] and r["tts_audio_ms"] == 1500
    assert r["tts_ttfb_ms"] == 300                            # 首包耗时取第一段
    assert {k for k, _, _ in objects.put_calls} == {"p/qa/tts/1002/7/T1.wav"}      # 同一个键，后一次覆盖前一次
    with wave.open(io.BytesIO(objects.put_calls[-1][1])) as w:
        assert w.getnframes() == 24000


async def test_an_interrupted_segment_marks_the_turn_interrupted(sqlite_engine):
    a, _ = archiver(sqlite_engine)
    await call(a, segment=seg(completed=False))
    assert (await rows(sqlite_engine))[0]["interrupted"]


async def test_a_failed_upload_keeps_the_text_and_does_not_claim_there_is_audio(sqlite_engine):
    a, _ = archiver(sqlite_engine, objects=Objects(fail=True))
    await call(a)
    (r,) = await rows(sqlite_engine)
    assert r["tts_text"] == ["先歇一会儿。"] and r["audio_out_key"] is None


async def test_no_object_store_means_text_only(sqlite_engine):
    a = TtsArchiver(qa=SqlQaStore(sqlite_engine), compliance=Compliance(True), objects=None)
    await call(a)
    (r,) = await rows(sqlite_engine)
    assert r["tts_text"] == ["先歇一会儿。"] and r["audio_out_key"] is None


async def test_a_segment_without_audio_records_text_and_no_key(sqlite_engine):
    a, objects = archiver(sqlite_engine)
    await call(a, segment=seg(pcm=b"", ttfb=None))
    (r,) = await rows(sqlite_engine)
    assert r["tts_text"] == ["先歇一会儿。"] and r["audio_out_key"] is None and objects.put_calls == []


async def test_old_turns_are_evicted_so_memory_stays_bounded(sqlite_engine):
    a, _ = archiver(sqlite_engine)
    for i in range(MAX_OPEN_TURNS + 3):
        await call(a, turn=f"T{i}")
    assert len(a._turns) == MAX_OPEN_TURNS
