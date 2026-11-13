"""模型调用与语音质检记录：内容看同意、到期清理、注销删除、音频键随之返回。"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from companion.adapters.store.sql.qa import SqlQaStore, VoiceTurnRecord
from companion.adapters.store.sql.schema import text_blob, turn_trace, voice_turn
from companion.domain.trace.model import LlmCall, build_trace


def _llm(seq=0, **kw) -> LlmCall:
    base = dict(seq=seq, provider="p", model="m", input_messages=[{"role": "human", "content": "今天好累"}],
                output_text="先歇一会儿", reasoning_text="用户情绪低落", input_tokens=120, output_tokens=18,
                cached_tokens=100, first_token_ms=420, total_ms=1300, finish_reason="stop")
    base.update(kw)
    return LlmCall(**base)


async def _age(engine, table, days, column="created_at"):
    """把一张表的全部行改成 ``days`` 天前，模拟已到期。"""
    async with engine.begin() as conn:
        await conn.execute(update(table).values(**{column: datetime.now(UTC) - timedelta(days=days)}))


async def _trace(store, turn="T1", owner=1002, *, keep=True, calls=None):
    return await store.record_trace(turn_id=turn, session_id=7, owner_id=owner, role_id="linche",
                                    calls=calls or [_llm()], keep_content=keep)


def _voice(turn="T1", owner=1002, **kw) -> VoiceTurnRecord:
    base = dict(turn_id=turn, session_id=7, owner_id=owner, role_id="linche", user_message_id=11,
                stt_provider="volc", stt_text="今天好累", stt_confidence=0.93,
                tts_provider="volc", tts_voice="saturn", tts_text=["先歇一会儿。"],
                audio_in_key="qa/in/1.wav", audio_out_key="qa/out/1.wav",
                first_sentence_ms=700, total_ms=2100)
    base.update(kw)
    return VoiceTurnRecord(**base)


async def _row(engine, table):
    async with engine.connect() as conn:
        return (await conn.execute(select(table))).mappings().all()


async def test_expired_rows_are_purged_with_their_audio_keys(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await _trace(store, "old")
    await store.record_voice_turn(_voice("old", audio_in_key="qa/in/old.wav", audio_out_key="qa/out/old.wav"),
                                  keep_content=True)
    await _age(sqlite_engine, turn_trace, 100)
    await _age(sqlite_engine, text_blob, 100, column="last_seen_at")
    await _age(sqlite_engine, voice_turn, 100)
    await _trace(store, "new", calls=[_llm(input_messages=[{"role": "human", "content": "新的一句"}])])
    await store.record_voice_turn(_voice("new", audio_in_key="qa/in/new.wav", audio_out_key="qa/out/new.wav"),
                                  keep_content=True)

    purged = await store.purge_before(cutoff=datetime.now(UTC) - timedelta(days=90))

    assert purged.rows >= 2
    assert purged.object_keys == ("qa/in/old.wav", "qa/out/old.wav")
    counts = await store.count()
    assert (counts["turn_trace"], counts["voice_turn"]) == (1, 1)
    assert [r["turn_id"] for r in await _row(sqlite_engine, turn_trace)] == ["new"]
    assert (await store.read_trace(turn_id="new"))["steps"][0]["input"][0]["content"] == "新的一句"


async def test_a_user_is_deleted_with_their_audio_and_nobody_else(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await _trace(store, "T1", 1002)
    await _trace(store, "T2", 1003)
    await store.record_voice_turn(_voice(owner=1002, audio_out_key="qa/out/a.wav", audio_in_key=""), keep_content=True)
    await store.record_voice_turn(_voice("T2", owner=1003, audio_out_key="qa/out/b.wav", audio_in_key=""),
                                  keep_content=True)

    assert await store.audio_keys_for_user(owner_id=1002) == ("qa/out/a.wav",)
    purged = await store.delete_user(owner_id=1002)

    assert purged.object_keys == ("qa/out/a.wav",)
    counts = await store.count()
    assert (counts["turn_trace"], counts["voice_turn"]) == (1, 1)
    assert await store.read_trace(turn_id="T1") is None and await store.read_trace(turn_id="T2") is not None
    assert await store.audio_keys_for_user(owner_id=1003) == ("qa/out/b.wav",)


class _Objects:
    def __init__(self, fail_on=()):
        self.deleted, self.fail_on = [], set(fail_on)

    async def delete(self, *, key):
        if key in self.fail_on:
            raise RuntimeError("tos down")
        self.deleted.append(key)


async def test_the_retention_job_deletes_rows_and_their_audio_objects(sqlite_engine):
    from companion.app.jobs.handlers import qa_purge

    store, objects = SqlQaStore(sqlite_engine), _Objects()
    await store.record_voice_turn(_voice("old", audio_in_key="a.wav", audio_out_key="b.wav"), keep_content=True)
    await _age(sqlite_engine, voice_turn, 120)
    await store.record_voice_turn(_voice("new", audio_in_key="c.wav", audio_out_key="d.wav"), keep_content=True)

    await qa_purge(store, retention_days=90, objects=objects)({})

    assert sorted(objects.deleted) == ["a.wav", "b.wav"]
    assert (await store.count())["voice_turn"] == 1


async def test_one_failing_object_delete_does_not_fail_the_job_or_skip_the_rest(sqlite_engine):
    from companion.app.jobs.handlers import qa_purge

    store, objects = SqlQaStore(sqlite_engine), _Objects(fail_on={"a.wav"})
    await store.record_voice_turn(_voice("old", audio_in_key="a.wav", audio_out_key="b.wav"), keep_content=True)
    await _age(sqlite_engine, voice_turn, 120)

    await qa_purge(store, retention_days=90, objects=objects)({})     # 不抛

    assert objects.deleted == ["b.wav"]
    assert (await store.count())["voice_turn"] == 0


async def test_account_footprint_includes_voice_audio_and_purge_removes_the_rows(sqlite_engine):
    from companion.adapters.store.sql.account import _OWNED, SqlAccountStore

    store = SqlQaStore(sqlite_engine)
    await _trace(store, "T1", 1002)
    await store.record_voice_turn(_voice(owner=1002, audio_out_key="qa/out/x.wav", audio_in_key=""), keep_content=True)

    foot = await SqlAccountStore(sqlite_engine).footprint(owner_id=1002)
    assert "qa/out/x.wav" in foot.object_keys               # 注销时和上传文件一起从对象存储删除
    assert turn_trace in _OWNED and text_blob in _OWNED and voice_turn in _OWNED     # 注销按 owner_id 删这几张表


# ---- 回合汇总 ca_chat_turn ----

def _turn_row(engine):
    from companion.adapters.store.sql.schema import chat_turn

    async def go():
        async with engine.connect() as conn:
            return (await conn.execute(select(chat_turn))).mappings().all()
    return go()


async def test_turn_summary_merges_usage_skills_and_final_state_in_either_order(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    calls = [_llm(seq=0, input_tokens=100, output_tokens=5, total_ms=400, tool_calls=[{"id": "c1", "name": "x"}]),
             _llm(seq=1, input_tokens=140, output_tokens=20, cached_tokens=100, total_ms=900)]
    steps, _ = build_trace(calls, keep_content=False)
    kw = dict(turn_id="TA", session_id=7, owner_id=1002, role_id="linche")
    # 先模型、后状态
    await store.note_turn_models(**kw, prompt_version="v1", skills=("companion-core", "active-listening"),
                                 steps=steps, started_at=datetime.now(UTC))
    await store.finish_turn(**kw, state="done")
    # 先状态、后模型（after_turn 先到的情况）
    await store.finish_turn(**{**kw, "turn_id": "TB"}, state="cancelled")
    await store.note_turn_models(**{**kw, "turn_id": "TB"}, prompt_version="v1", skills=("companion-core",),
                                 steps=steps[:1], started_at=datetime.now(UTC))

    rows = {r["id"]: r for r in await _turn_row(sqlite_engine)}
    a, b = rows["TA"], rows["TB"]
    assert a["state"] == "done" and a["finished_at"] is not None and a["started_at"] is not None
    assert a["skills"] == ["companion-core", "active-listening"] and a["prompt_version"] == "v1"
    assert a["usage"] == {"calls": 2, "input_tokens": 240, "output_tokens": 25, "cached_tokens": 200,
                          "llm_ms": 1300, "tool_calls": 1}
    assert b["state"] == "cancelled" and b["usage"]["calls"] == 1      # 状态没被后到的模型信息盖掉


async def test_a_turn_with_no_model_call_still_gets_its_final_state(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await store.finish_turn(turn_id="TC", session_id=7, owner_id=1002, role_id="linche", state="failed",
                            error_code="turn_failed")
    (row,) = await _turn_row(sqlite_engine)
    assert (row["state"], row["error_code"], row["usage"]) == ("failed", "turn_failed", None)


# ---- 工具调用 ----

# ---- 语音回合：识别方与 TTS 方按 turn_id 合并 ----

async def test_the_stt_side_and_the_tts_side_merge_into_one_row_in_either_order(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    stt = VoiceTurnRecord(turn_id="TA", session_id=7, owner_id=1002, role_id="linche", user_message_id=11,
                          stt_text="今天好累", stt_confidence=0.9, first_sentence_ms=700, total_ms=2100)
    tts = VoiceTurnRecord(turn_id="TA", session_id=7, owner_id=1002, tts_provider="volc", tts_voice="saturn",
                          tts_text=["先歇一会儿。"], audio_out_key="qa/a.wav", tts_ttfb_ms=300, tts_audio_ms=2500)
    await store.record_voice_turn(stt, keep_content=True)
    await store.record_voice_turn(tts, keep_content=True)
    # 反过来：TTS 方先到
    await store.record_voice_turn(VoiceTurnRecord(**{**tts.__dict__, "turn_id": "TB"}), keep_content=True)
    await store.record_voice_turn(VoiceTurnRecord(**{**stt.__dict__, "turn_id": "TB"}), keep_content=True)

    rows = {r["turn_id"]: r for r in await _row(sqlite_engine, voice_turn)}
    assert len(rows) == 2
    for r in rows.values():
        assert (r["stt_text"], r["stt_confidence"], r["first_sentence_ms"]) == ("今天好累", 0.9, 700)
        assert (r["tts_text"], r["audio_out_key"], r["tts_ttfb_ms"], r["tts_audio_ms"]) == (["先歇一会儿。"], "qa/a.wav", 300, 2500)
        assert (r["user_message_id"], r["role_id"], r["tts_voice"]) == (11, "linche", "saturn")


async def test_a_later_write_does_not_blank_what_the_other_side_wrote(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await store.record_voice_turn(_voice(), keep_content=True)
    await store.record_voice_turn(VoiceTurnRecord(turn_id="T1", session_id=7, owner_id=1002, tts_ttfb_ms=250), keep_content=True)
    (row,) = await _row(sqlite_engine, voice_turn)
    assert row["stt_text"] == "今天好累" and row["tts_text"] == ["先歇一会儿。"] and row["tts_ttfb_ms"] == 250


async def test_interruption_can_only_be_set_never_cleared_by_the_other_side(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await store.record_voice_turn(VoiceTurnRecord(turn_id="T1", session_id=7, owner_id=1002, interrupted=True), keep_content=False)
    await store.record_voice_turn(VoiceTurnRecord(turn_id="T1", session_id=7, owner_id=1002, total_ms=900), keep_content=False)
    (row,) = await _row(sqlite_engine, voice_turn)
    assert row["interrupted"]
