"""协议 v2 的 speech.* 接线在 agent 上的行为：先声明后出声、正常结束 end、被打断 cancel。

测试直接用 :func:`build_agent_class` 造真的 Agent 子类，只替换管线与 TTS 默认实现。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from livekit.agents import Agent

from companion.api.livekit.agent import build_agent_class
from test_voice_record import Pipeline, _fake_default, _frames, _settle, _synthesize, _texts


class _Speech:
    """记录 agent 对 SpeechPublisher 的调用顺序。"""

    def __init__(self, *, declare: bool = True) -> None:
        self.events: list[str] = []
        self._declare = declare
        self._idx = 0
        self.speech_id = "sp_test"

    async def start_reply(self) -> None:
        self.events.append("start_reply")

    async def say(self, text: str, *, turn_id: str):
        self.events.append(f"say:{text}:{turn_id}")
        if not self._declare:
            return None
        from companion.agent.protocol.speech_plan import PlannedSegment, estimate_ms

        seg = PlannedSegment(idx=self._idx, text=text, est_ms=estimate_ms(text))
        self._idx += 1
        return self.speech_id, seg

    async def finish(self) -> None:
        self.events.append("finish")

    async def cancel(self, reason: str = "user_barge_in") -> None:
        self.events.append(f"cancel:{reason}")


class _Cues:
    """记录锚点 cue 发布顺序。"""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.calls: list[dict] = []

    def reset_turn(self) -> None:
        self.events.append("reset_turn")

    async def publish_for_segment(self, intents, *, speech_id: str, seg_idx: int, source: str = "tag") -> int:
        names = [getattr(i, "name", "?") for i in intents]
        self.events.append(f"cue:{speech_id}:{seg_idx}:{','.join(names)}:{source}")
        self.calls.append(
            {"intents": list(intents), "speech_id": speech_id, "seg_idx": seg_idx, "source": source}
        )
        return len(intents)


class _CancellablePipeline(Pipeline):
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.cancelled = 0

    async def cancel(self) -> None:
        self.cancelled += 1


CTX = SimpleNamespace(items=[SimpleNamespace(role="user", text_content="今天好累")])
EMPTY_CTX = SimpleNamespace(items=[])


def _agent(pipeline, speech):
    return build_agent_class()(
        pipeline=pipeline, user_id="1002", character_id="linche", chat_session_id=42, speech=speech,
    )


async def test_each_sentence_is_declared_before_the_agent_yields_it():
    speech = _Speech()
    agent = _agent(Pipeline(sentences=("先歇一会儿。", "我在。")), speech)

    seen: list[str] = []
    async for text in agent.llm_node(CTX, [], None):
        seen.append(text)
        speech.events.append(f"got:{text}")

    assert speech.events == [
        "start_reply",
        "say:先歇一会儿。:T1",
        "got:先歇一会儿。",
        "say:我在。:T1",
        "got:我在。",
    ]
    assert seen == ["先歇一会儿。", "我在。"]


async def test_anchored_cues_publish_after_say_before_yield():
    """§13 不变量 1：speech.seg → presentation.*（带 at）→ TTS yield。"""
    from companion.agent.protocol.cue_intent import CueIntent

    speech = _Speech()
    cues = _Cues()
    intent = CueIntent(kind="emotion", name="joy", phase="start")
    pipeline = Pipeline(sentences=("先歇一会儿。",))

    class _WithIntents(Pipeline):
        async def run(self, request):
            yield SimpleNamespace(
                text="先歇一会儿。",
                events=[],
                intents=[intent],
                source="tag",
            )

    agent = build_agent_class()(
        pipeline=_WithIntents(),
        user_id="1002",
        character_id="linche",
        chat_session_id=42,
        speech=speech,
        cues=cues,
    )

    seen: list[str] = []
    async for text in agent.llm_node(CTX, [], None):
        seen.append(text)
        speech.events.append(f"got:{text}")

    assert speech.events == [
        "start_reply",
        "say:先歇一会儿。:T1",
        "got:先歇一会儿。",
    ]
    assert cues.events == [
        "reset_turn",
        "cue:sp_test:0:joy:tag",
    ]
    assert cues.calls[0]["seg_idx"] == 0
    assert cues.calls[0]["speech_id"] == "sp_test"
    assert seen == ["先歇一会儿。"]


async def test_no_turn_handle_means_text_still_plays_but_nothing_is_declared():
    speech = _Speech()
    agent = _agent(Pipeline(sentences=("好的。",), turn_id=None), speech)

    out = [t async for t in agent.llm_node(CTX, [], None)]

    assert out == ["好的。"]
    assert not any(e.startswith("say:") for e in speech.events)


async def test_empty_user_message_starts_no_reply(monkeypatch):
    speech = _Speech()
    agent = _agent(Pipeline(), speech)

    out = [t async for t in agent.llm_node(EMPTY_CTX, [], None)]

    assert out == []
    assert speech.events == []


async def test_first_tts_frame_is_logged_with_its_delay(caplog, monkeypatch):
    """首帧时刻单独记一行：`tts done` 在回合末尾才出现，量不出引擎首包多久。

    RCA 的 ③ 段（tts start→首个有能量帧）全靠这一行；早停（打断）也要有。"""
    import logging

    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(2)), raising=True)
    speech = _Speech()
    agent = _agent(Pipeline(), speech)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        await _synthesize(agent)

    (line,) = [r.message for r in caplog.records if "tts first" in r.message]
    assert "turn=T1" in line and "first_frame_ms=" in line


async def test_first_tts_frame_is_logged_even_when_the_turn_is_interrupted(caplog, monkeypatch):
    """被打断只剩一帧也要有首帧行——F16 要量的正是「引擎什么时候开始出帧」。"""
    import logging

    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(5)), raising=True)
    speech = _Speech()
    agent = _agent(Pipeline(), speech)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        node = await agent.tts_node(_texts("先歇一会儿"), None)
        await node.__anext__()
        await node.aclose()

    (line,) = [r.message for r in caplog.records if "tts first" in r.message]
    assert "turn=T1" in line and "first_frame_ms=" in line


async def test_tts_that_runs_to_the_end_finishes_the_speech(monkeypatch):
    """帧迭代正常结束 → finish → speech.end（§9.3 生成侧排空）。

    这是服务端能承诺的唯一「说完」：音频帧已全部 yield。端侧扬声器是否播完
    不在这里、也不该被假装成在这里。
    """
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(2)), raising=True)
    speech = _Speech()
    agent = _agent(Pipeline(), speech)

    frames = await _synthesize(agent)
    await _settle(agent)

    assert len(frames) == 2
    assert speech.events == ["finish"]


async def test_closing_tts_early_cancels_the_speech_not_finishes_it(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(5)), raising=True)
    speech = _Speech()
    agent = _agent(Pipeline(), speech)

    node = await agent.tts_node(_texts("先歇一会儿"), None)
    await node.__anext__()
    await node.aclose()              # 用户打断：框架关闭生成器
    await _settle(agent)

    assert speech.events == ["cancel:user_barge_in"]


async def test_tts_error_mid_stream_cancels_the_speech(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(5), fail_after=1), raising=True)
    speech = _Speech()
    agent = _agent(Pipeline(), speech)

    with pytest.raises(RuntimeError):
        await _synthesize(agent)
    await _settle(agent)

    assert speech.events == ["cancel:user_barge_in"]


async def test_cancel_turn_cancels_speech_and_pipeline(monkeypatch):
    speech = _Speech()
    pipeline = _CancellablePipeline()
    agent = _agent(pipeline, speech)

    await agent.cancel_turn()

    assert speech.events == ["cancel:user_barge_in"]
    assert pipeline.cancelled == 1


async def test_without_a_speech_publisher_the_agent_still_speaks(monkeypatch):
    monkeypatch.setattr(Agent.default, "tts_node", _fake_default(_frames(2)), raising=True)
    agent = build_agent_class()(pipeline=Pipeline(), user_id="1002", character_id="linche", chat_session_id=42)

    out = [t async for t in agent.llm_node(CTX, [], None)]
    frames = await _synthesize(agent)

    assert out == ["先歇一会儿。", "我在。"]
    assert len(frames) == 2


async def test_turn_logs_user_words_and_the_reply(caplog):
    """通话排障的基本盘：日志里必须能直接看到用户说的话和回复的内容。

    QA 库受"用户同意留存内容"门控，日志是运维唯一的现场；缺了这两行，
    「她听错了什么」只能靠复现。"""
    import logging

    speech = _Speech()
    agent = _agent(Pipeline(sentences=("先歇一会儿。", "我在。")), speech)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        async for _ in agent.llm_node(CTX, [], None):
            pass

    lines = [r.message for r in caplog.records if "voice turn" in r.message or "voice reply" in r.message]
    assert len(lines) == 2, lines
    assert "今天好累" in lines[0] and "said=" in lines[0]
    assert "先歇一会儿。" in lines[1] and "interrupted=False" in lines[1]


async def test_turn_log_clips_long_transcripts(caplog):
    import logging

    long = "累" * 500
    ctx = SimpleNamespace(items=[SimpleNamespace(role="user", text_content=long)])
    agent = _agent(Pipeline(sentences=("好的。",)), _Speech())
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        async for _ in agent.llm_node(ctx, [], None):
            pass

    said = next(r.message for r in caplog.records if "voice turn" in r.message)
    assert "(+300)" in said and "\n" not in said


async def test_voice_reply_line_reports_the_cue_outcome(caplog):
    """「表情没出来」的三种成因必须一眼分开：模型没出 cue、锚点没声明、闸掉了。

    11-23 三个 job 的 `voice reply` 行里 cue 去向完全看不见，对账只能拿
    「grep 不到 presentation.emotion」反推——而那条 grep 对正常发送也永远是空。
    回复行直接带 cues=发出/意图，每回合一条，不再靠反推。
    """
    import logging
    from companion.agent.protocol.cue_intent import CueIntent

    speech = _Speech()
    cues = _Cues()

    class _WithIntents:
        def __init__(self):
            self.last_turn = SimpleNamespace(turn_id="T1", user_message_id=None)

        async def run(self, request):
            yield SimpleNamespace(text="先歇一会儿。", events=[],
                                  intents=[CueIntent(kind="emotion", name="joy")], source="structured")

        async def cancel(self) -> None:
            return None

    agent = build_agent_class()(pipeline=_WithIntents(), user_id="1002", character_id="linche",
                                chat_session_id=42, speech=speech, cues=cues)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        async for _ in agent.llm_node(CTX, [], None):
            pass

    reply = next(r.message for r in caplog.records if "voice reply" in r.message)
    assert "cues=1/1" in reply, reply


async def test_a_reply_without_cue_intents_says_so(caplog):
    """模型没出 cue（intents 空）要在同一行显式记 cues=0/0，而不是靠 absence 推断。"""
    import logging

    speech = _Speech()
    agent = _agent(Pipeline(sentences=("先歇一会儿。",)), speech)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        async for _ in agent.llm_node(CTX, [], None):
            pass

    reply = next(r.message for r in caplog.records if "voice reply" in r.message)
    assert "cues=0/0" in reply, reply


# 生产 session-33 / turn 01M86MPWW7FD0DS4WH2979MVWM 的 checkpoint 原文：模型确实
# 输出了两行 cue JSON，voice.log 却是 cues=0/0。F16（7ef3ace）后守卫提前流式 say，
# cues 随空正文壳 {"say":"","cues":[…]} 到达——它们必须补挂到刚声明的那一段。
PROD_LINE = (
    '{"say":"我们在多个县。","cues":[{"kind":"gaze","name":"look_user","anchor":"segment_start"}]} '
    '{"say":"你是说你们分布覆盖了好几个县？","cues":[{"kind":"gesture","name":"nod","anchor":"segment_start"}]}'
)


async def test_cue_shells_from_streamed_say_publish_on_their_segment(caplog):
    """F16 空壳里的 cue 不能因 text 为空被吞：生产 cue JSON → cues=2/2 + 两段都发。

    守卫把 say 提前放给断句器，闭合后只回 ``{"say":"","cues":[…]}``。llm_node 以前
    把意图计数与发送都写在 ``if output.text:`` 里——空壳整个被跳过，模型出的 cue
    就在这里静默消失（session-33 的 cue JSON 变成 cues=0/0 的确切路径）。
    """
    import logging

    from companion.agent.brain.fake import FakeBrain
    from companion.service.turn.pipeline import TurnPipeline

    speech = _Speech()
    cues = _Cues()
    chunks = [PROD_LINE[i:i + 7] for i in range(0, len(PROD_LINE), 7)]
    agent = build_agent_class()(
        pipeline=TurnPipeline(FakeBrain(chunks)),
        user_id="1002", character_id="linche", chat_session_id=42,
        speech=speech, cues=cues,
    )

    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        seen = [t async for t in agent.llm_node(CTX, [], None)]

    assert cues.events == [
        "reset_turn",
        "cue:sp_test:0:look_user:structured",
        "cue:sp_test:1:nod:structured",
    ], cues.events
    assert cues.calls[0]["seg_idx"] == 0 and cues.calls[1]["seg_idx"] == 1
    reply = next(r.message for r in caplog.records if "voice reply" in r.message)
    assert "cues=2/2" in reply, reply
    assert "我们在多个县" in reply and "你是说你们分布覆盖了" in reply, reply


async def test_cue_shell_before_any_declared_segment_counts_but_sends_nothing(caplog):
    """正文还没声明过 seg 就来的 cue 壳：意图计数照常（cues=0/1），不凭空发布。

    这是 44d2d27 三种成因口径的另一半——「锚点没声明」必须在计数里看得见，
    否则 cues=0/0 又把「模型没出」和「没处挂」混回一行。
    """
    import logging
    from companion.agent.protocol.cue_intent import CueIntent

    speech = _Speech()
    cues = _Cues()

    class _ShellFirst:
        def __init__(self):
            self.last_turn = SimpleNamespace(turn_id="T1", user_message_id=None)

        async def run(self, request):
            yield SimpleNamespace(text="", events=[],
                                  intents=[CueIntent(kind="emotion", name="joy")], source="structured")
            yield SimpleNamespace(text="先歇一会儿。", events=[], intents=[], source="tag")

        async def cancel(self) -> None:
            return None

    agent = build_agent_class()(pipeline=_ShellFirst(), user_id="1002", character_id="linche",
                                chat_session_id=42, speech=speech, cues=cues)
    with caplog.at_level(logging.INFO, logger="companion.api.livekit.agent"):
        seen = [t async for t in agent.llm_node(CTX, [], None)]

    assert seen == ["先歇一会儿。"]
    assert cues.events == ["reset_turn"], cues.events
    reply = next(r.message for r in caplog.records if "voice reply" in r.message)
    assert "cues=0/1" in reply, reply
