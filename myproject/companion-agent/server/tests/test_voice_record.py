"""语音回合的质检记录：谁来写、记什么、同意之前不留什么、被打断时仍然记。"""

import asyncio
from types import SimpleNamespace

from companion.trace.qa import SqlQaStore, VoiceTurnRecord
from companion.adapters.store.sql.schema import voice_turn
from companion.api.livekit.agent import build_agent_class
from companion.bootstrap.voice_wiring import build_voice_recorder
from companion.brain.port import BrainTurn
from sqlalchemy import select


class Pipeline:
    """按脚本吐句子，并像真实管线一样在 last_turn 上留下回合句柄。"""

    def __init__(self, sentences=("先歇一会儿。", "我在。"), turn_id="T1", message_id=11, error=None, stall=False):
        self.sentences, self.error, self.stall = sentences, error, stall
        self.last_turn = BrainTurn(tokens=None, cancel=None, turn_id=turn_id, user_message_id=message_id) if turn_id else None

    async def run(self, request):
        if self.error:
            raise self.error
        for s in self.sentences:
            yield SimpleNamespace(text=s, events=[])
        if self.stall:
            await asyncio.sleep(30)


class Recorder:
    def __init__(self):
        self.records: list[VoiceTurnRecord] = []

    async def __call__(self, rec):
        self.records.append(rec)


def _agent(pipeline, recorder):
    return build_agent_class()(pipeline=pipeline, user_id="1002", character_id="linche", chat_session_id=42,
                               recorder=recorder)


CTX = SimpleNamespace(items=[SimpleNamespace(role="user", text_content="今天好累")])


async def _say(agent):
    return [s async for s in agent.llm_node(CTX, [], None)]


async def _settle(agent):
    await asyncio.gather(*list(agent._background))


async def test_a_finished_turn_records_what_was_recognised_and_what_was_sent_to_tts():
    rec = Recorder()
    agent = _agent(Pipeline(), rec)
    await _say(agent)
    await _settle(agent)

    (r,) = rec.records
    assert (r.turn_id, r.session_id, r.owner_id, r.role_id, r.user_message_id) == ("T1", 42, 1002, "linche", 11)
    assert r.stt_text == "今天好累"
    assert r.tts_text is None       # 真正送进 TTS 的文本由 tts_node 那一方记录，不用 llm_node 的版本
    assert not r.interrupted
    assert r.first_sentence_ms is not None and r.first_sentence_ms <= r.total_ms


async def test_an_interrupted_turn_is_still_recorded_with_what_was_already_sent():
    rec = Recorder()
    agent = _agent(Pipeline(stall=True), rec)
    gen = agent.llm_node(CTX, [], None)
    assert await gen.__anext__() == "先歇一会儿。"
    await gen.aclose()                       # 用户打断：框架关闭生成器
    await _settle(agent)

    (r,) = rec.records
    assert r.interrupted is True


async def test_a_refused_input_has_no_turn_so_nothing_is_recorded():
    from companion.brain.port import TurnRefused

    rec = Recorder()
    agent = _agent(Pipeline(error=TurnRefused("blocked"), turn_id=""), rec)
    await _say(agent)
    await _settle(agent)
    assert rec.records == []


async def test_a_recorder_that_fails_does_not_break_the_call():
    async def boom(rec):
        raise RuntimeError("db down")

    agent = _agent(Pipeline(), boom)
    assert await _say(agent) == ["先歇一会儿。", "我在。"]
    await _settle(agent)                      # 任务内部吞掉异常，不会抛出来


async def test_no_recorder_means_no_background_work():
    agent = _agent(Pipeline(), None)
    await _say(agent)
    assert not agent._background


# ---- 写入口：同意之前不留内容 ----

class Compliance:
    def __init__(self, allowed):
        self.allowed = allowed

    async def qa_content_allowed(self, *, owner_id):
        return self.allowed


def _record():
    return VoiceTurnRecord(turn_id="T1", session_id=42, owner_id=1002, role_id="linche", user_message_id=11,
                           stt_text="今天好累", tts_text=["先歇一会儿。"], audio_out_key="qa/x.wav")


async def _stored(engine):
    async with engine.connect() as conn:
        return (await conn.execute(select(voice_turn))).mappings().one()


INFO = {"stt_provider": "volcengine", "tts_provider": "volcengine", "tts_voice": "saturn"}


async def test_without_consent_only_providers_and_timings_are_stored(sqlite_engine):
    platform = SimpleNamespace(qa=SqlQaStore(sqlite_engine), compliance=Compliance(False))
    await build_voice_recorder(platform, INFO)(_record())

    row = await _stored(sqlite_engine)
    assert not row["content_kept"] and row["stt_text"] is None and row["tts_text"] is None
    assert row["audio_out_key"] is None
    assert (row["stt_provider"], row["tts_provider"], row["tts_voice"]) == ("volcengine", "volcengine", "saturn")


async def test_with_consent_the_texts_are_stored(sqlite_engine):
    platform = SimpleNamespace(qa=SqlQaStore(sqlite_engine), compliance=Compliance(True))
    await build_voice_recorder(platform, INFO)(_record())

    row = await _stored(sqlite_engine)
    assert row["content_kept"] and row["stt_text"] == "今天好累" and row["tts_text"] == ["先歇一会儿。"]
    assert row["user_message_id"] == 11


async def test_no_compliance_service_fails_closed(sqlite_engine):
    platform = SimpleNamespace(qa=SqlQaStore(sqlite_engine), compliance=None)
    await build_voice_recorder(platform, INFO)(_record())
    assert (await _stored(sqlite_engine))["stt_text"] is None


def test_without_a_qa_store_there_is_no_recorder():
    assert build_voice_recorder(SimpleNamespace(qa=None, compliance=None), INFO) is None


def test_the_worker_builds_voice_info_without_crashing():
    """main() 里拼 voice_info 用到了 os；它曾只在另一个函数里局部导入，到启动时才 NameError。"""
    import companion.worker as worker

    assert hasattr(worker, "os")


# ---- tts_node：采集“送进合成引擎的文本 + 出来的音频” ----

from livekit.agents import Agent


def _frames(n=2, rate=16000):
    return [SimpleNamespace(data=b"\x01\x00" * 1600, sample_rate=rate, num_channels=1) for _ in range(n)]


def _fake_default(frames, *, fail_after=None, seen=None):
    """代替 Agent.default.tts_node：读完输入文本，吐出音频帧。和真实实现一样是异步生成器。"""
    async def default(agent, text, model_settings):
        got = [chunk async for chunk in text]
        if seen is not None:
            seen.extend(got)
        for i, f in enumerate(frames):
            if fail_after is not None and i >= fail_after:
                raise RuntimeError("engine down")
            yield f
    return default


async def _texts(*chunks):
    for c in chunks:
        yield c


class Sink:
    def __init__(self):
        self.calls = []

    async def __call__(self, **kw):
        self.calls.append(kw)


async def _synthesize(agent, chunks=("先歇一会儿。", "我在。")):
    node = agent.tts_node(_texts(*chunks), None)
    if hasattr(node, "__await__"):          # 框架：协程就先 await 拿到生成器
        node = await node
    return [f async for f in node]


async def test_tts_node_plays_every_frame_and_reports_text_audio_and_turn(monkeypatch):
    seen = []
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(), seen=seen), raising=True)
    sink = Sink()
    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42, tts_sink=sink)

    played = await _synthesize(agent)
    await _settle(agent)

    assert len(played) == 2 and seen == ["先歇一会儿。", "我在。"]          # 放出去的和默认实现看到的一样
    (call,) = sink.calls
    assert (call["turn_id"], call["session_id"], call["owner_id"], call["role_id"], call["user_message_id"]) == ("T1", 42, 1002, "linche", 11)
    seg = call["segment"]
    assert seg.text == "先歇一会儿。我在。" and seg.completed and len(seg.pcm) == 2 * 3200 and seg.audio_ms == 200


async def test_without_a_sink_the_default_tts_node_is_returned_untouched(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(Agent.default, "tts_node", lambda agent, text, ms: sentinel)
    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42)
    node = agent.tts_node(_texts("x"), None)
    if hasattr(node, "__await__"):        # 框架先判断 iscoroutine 再 await，这里照做
        node = await node
    assert node is sentinel
    assert not agent._background


async def test_an_engine_failure_is_still_reported_as_an_incomplete_segment(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(3), fail_after=1), raising=True)
    sink = Sink()
    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42, tts_sink=sink)

    node = await agent.tts_node(_texts("你好"), None)
    try:
        [f async for f in node]
    except RuntimeError:
        pass
    await _settle(agent)
    assert sink.calls[0]["segment"].completed is False and len(sink.calls[0]["segment"].pcm) == 3200


async def test_closing_the_stream_early_reports_an_interrupted_segment(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(5)), raising=True)
    sink = Sink()
    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42, tts_sink=sink)

    node = await agent.tts_node(_texts("先歇一会儿"), None)
    await node.__anext__()
    await node.aclose()                      # 用户打断：框架关闭生成器
    await _settle(agent)
    seg = sink.calls[0]["segment"]
    assert seg.completed is False and seg.text == "先歇一会儿"


async def test_a_synthesis_with_no_turn_is_not_attributed_to_a_stale_one(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames()), raising=True)
    sink = Sink()
    agent = build_agent_class()(pipeline=Pipeline(turn_id=""), user_id="1002", character_id="linche", chat_session_id=42, tts_sink=sink)
    await _synthesize(agent)
    await _settle(agent)
    assert sink.calls == []


async def test_a_failing_sink_does_not_break_playback(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames()), raising=True)

    async def boom(**kw):
        raise RuntimeError("db down")

    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42, tts_sink=boom)
    assert len(await _synthesize(agent)) == 2
    await _settle(agent)


# ---- STT 置信度 ----

def test_stt_confidence_zero_or_missing_means_unknown_not_zero():
    from companion.api.livekit.agent import last_user_confidence

    ctx = lambda v: SimpleNamespace(items=[SimpleNamespace(role="user", transcript_confidence=v)])
    assert last_user_confidence(ctx(0.93)) == 0.93
    assert last_user_confidence(ctx(0.0)) is None          # 插件没返回时框架给的 0.0
    assert last_user_confidence(ctx(None)) is None
    assert last_user_confidence(SimpleNamespace(items=[])) is None
    assert last_user_confidence(SimpleNamespace(items=[SimpleNamespace(role="user")])) is None


async def test_the_recognition_confidence_reaches_the_voice_record():
    rec = Recorder()
    agent = _agent(Pipeline(), rec)
    ctx = SimpleNamespace(items=[SimpleNamespace(role="user", text_content="今天好累", transcript_confidence=0.87)])
    [s async for s in agent.llm_node(ctx, [], None)]
    await _settle(agent)
    assert rec.records[0].stt_confidence == 0.87


# ---- .env 载入 ----

def test_load_env_fills_missing_variables_but_never_overrides_real_ones(tmp_path, monkeypatch):
    from companion.worker import load_env

    f = tmp_path / ".env"
    f.write_text('VOLC_TEST_A="from-file"\nVOLC_TEST_B=from-file\nVOLC_TEST_EMPTY\n')
    monkeypatch.delenv("VOLC_TEST_A", raising=False)
    monkeypatch.setenv("VOLC_TEST_B", "from-platform")        # 部署平台注入的值
    monkeypatch.delenv("VOLC_TEST_EMPTY", raising=False)

    assert load_env(f) == 1
    import os
    assert os.environ["VOLC_TEST_A"] == "from-file" and os.environ["VOLC_TEST_B"] == "from-platform"
    assert "VOLC_TEST_EMPTY" not in os.environ                 # 没有值的行不载入
    monkeypatch.delenv("VOLC_TEST_A", raising=False)


def test_load_env_with_no_file_is_a_noop(tmp_path):
    from companion.worker import load_env

    assert load_env(tmp_path / "missing.env") == 0
