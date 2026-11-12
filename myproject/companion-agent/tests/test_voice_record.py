"""语音回合的质检记录：谁来写、记什么、同意之前不留什么、被打断时仍然记。"""

import asyncio
from types import SimpleNamespace

from companion.adapters.store.sql.qa import SqlQaStore, VoiceTurnRecord
from companion.adapters.store.sql.schema import voice_turn
from companion.api.livekit.agent import build_agent_class
from companion.api.livekit.entrypoint import build_voice_recorder
from companion.ports.brain import BrainTurn
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
    assert r.stt_text == "今天好累" and r.tts_text == ["先歇一会儿。", "我在。"]
    assert r.interrupted is False
    assert r.first_sentence_ms is not None and r.first_sentence_ms <= r.total_ms


async def test_an_interrupted_turn_is_still_recorded_with_what_was_already_sent():
    rec = Recorder()
    agent = _agent(Pipeline(stall=True), rec)
    gen = agent.llm_node(CTX, [], None)
    assert await gen.__anext__() == "先歇一会儿。"
    await gen.aclose()                       # 用户打断：框架关闭生成器
    await _settle(agent)

    (r,) = rec.records
    assert r.interrupted is True and r.tts_text == ["先歇一会儿。"]


async def test_a_refused_input_has_no_turn_so_nothing_is_recorded():
    from companion.adapters.brain.platform_brain import TurnRefused

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
