"""语音回合走文字同一条路：``PlatformBrain`` 把 ``BrainPort`` 接到 ``SubmitService`` + 事件流。

要证明的是三件事，都不需要真实 Redis / Postgres：

1. 语音说的话经 ``submit`` 提交（所以会落 ``ca_chat_message``、拿会话锁、走 ``after_turn``），
   而不是像旧的 ``TurnPipeline`` 直连大脑那样“说完就丢”。
2. 朗读的内容来自同一回合的 ``message.delta``，别的回合的事件不会串进来。
3. 用户打断时取消的是这一回合。
"""

import asyncio
from types import SimpleNamespace

import pytest

from companion.service.turn.queue import Disposition
from companion.agent.brain.port import TurnRequest

SESSION = 7
TURN = "01TURNAAAAAAAAAAAAAAAAAAAA"


class FakeControl:
    """只实现 PlatformBrain 用到的事件流部分。事件 id 是递增的 "n-0"。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []
        self.cancelled: list[str] = []

    def add(self, name: str, **data) -> None:
        self.events.append((f"{len(self.events) + 1}-0", name, data))

    async def tail_event_id(self, *, session_id: int) -> str:
        return self.events[-1][0] if self.events else "0-0"

    async def wait_events(self, *, session_id: int, after_id: str, block_ms: int):
        after = int(after_id.split("-")[0])
        found = [e for e in self.events if int(e[0].split("-")[0]) > after]
        if not found:
            await asyncio.sleep(0.01)
        return found

    async def send_cancel(self, *, turn_id: str) -> None:
        self.cancelled.append(turn_id)


class FakeSubmit:
    """记录提交；提交成功后按脚本往事件流里“放”回合事件，模拟 TurnRunner。"""

    def __init__(self, control: FakeControl, script, *, status="accepted",
                 disposition=Disposition.STARTED, turn_id=TURN) -> None:
        self.control, self.script = control, script
        self.status, self.disposition, self.turn_id = status, disposition, turn_id
        self.calls: list[dict] = []

    async def submit(self, **kw):
        self.calls.append(kw)
        if self.status == "accepted":
            self.script(self.control)
        return SimpleNamespace(status=self.status, disposition=self.disposition, message_id=11,
                               turn_id=self.turn_id, reason="blocked" if self.status == "denied" else None)


def _brain(control, submit):
    from companion.service.turns.platform_brain import PlatformBrain

    return PlatformBrain(submit=submit, control=control)


def _request(text="今天好累", session_id=SESSION) -> TurnRequest:
    return TurnRequest(user_id="1002", character_id="linche", message=text, session_id=session_id)


async def _collect(turn) -> str:
    return "".join([chunk async for chunk in turn.tokens])


def _happy(control: FakeControl) -> None:
    control.add("turn.started", turn_id=TURN)
    control.add("message.delta", turn_id=TURN, delta="先歇一会儿，")
    control.add("message.delta", turn_id=TURN, delta="我在。")
    control.add("message.done", turn_id=TURN, assistant_message_id=12)


async def test_spoken_text_is_submitted_like_a_typed_message():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    turn = await _brain(control, submit).start_turn(_request())
    await _collect(turn)

    call = submit.calls[0]
    assert (call["owner_id"], call["session_id"], call["character_id"], call["text"]) == (
        1002, SESSION, "linche", "今天好累")
    # 语音一次说一句：不插话、不合并，会话忙就等，和文字输入框里“不可插话”的行为一致
    assert call["steerable"] is False
    # 转写文字要能和打字区分开
    assert call["kind"] == "voice"


async def test_tokens_are_the_deltas_of_this_turn():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    turn = await _brain(control, submit).start_turn(_request())
    assert await _collect(turn) == "先歇一会儿，我在。"
    assert turn.turn_id == TURN


async def test_events_of_another_turn_do_not_leak_in():
    def script(control: FakeControl) -> None:
        control.add("message.delta", turn_id="OTHER", delta="别人的话")
        _happy(control)
        control.add("message.delta", turn_id="OTHER", delta="之后的别人的话")

    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, script)).start_turn(_request())
    assert await _collect(turn) == "先歇一会儿，我在。"


async def test_old_events_before_the_submit_are_ignored():
    control = FakeControl()
    control.add("message.delta", turn_id=TURN, delta="上一次遗留")
    control.add("message.done", turn_id=TURN)
    turn = await _brain(control, FakeSubmit(control, _happy)).start_turn(_request())
    assert await _collect(turn) == "先歇一会儿，我在。"


async def test_an_error_event_ends_the_stream_but_keeps_what_was_said():
    def script(control: FakeControl) -> None:
        control.add("message.delta", turn_id=TURN, delta="我想说")
        control.add("error", turn_id=TURN, code="model_unavailable")

    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, script)).start_turn(_request())
    assert await _collect(turn) == "我想说"


async def test_a_cancelled_turn_ends_the_stream():
    def script(control: FakeControl) -> None:
        control.add("message.delta", turn_id=TURN, delta="我想")
        control.add("turn.cancelled", turn_id=TURN)

    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, script)).start_turn(_request())
    assert await _collect(turn) == "我想"


async def test_interrupting_cancels_this_turn_on_the_control_plane():
    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, lambda c: c.add("turn.started", turn_id=TURN))
                        ).start_turn(_request())
    await turn.cancel_turn()
    assert control.cancelled == [TURN]


async def test_denied_input_is_not_spoken_and_not_silent():
    from companion.agent.brain.port import TurnRefused

    control = FakeControl()
    with pytest.raises(TurnRefused) as info:
        await _brain(control, FakeSubmit(control, _happy, status="denied", disposition=None, turn_id=None)
                     ).start_turn(_request())
    assert info.value.reason == "blocked"


async def test_a_queued_turn_waits_for_drain_and_streams_that_reply():
    # 会话正忙：这句话先排队。drain 之后会发 turn.started(user_message_ids 含本条)，
    # 语音必须挂等并朗读那一轮——否则端上就是 remote PCM=0 / said=''。
    control = FakeControl()
    submit = FakeSubmit(control, lambda _c: None, disposition=Disposition.QUEUED, turn_id=None)
    turn = await _brain(control, submit).start_turn(_request())
    drained = "01DRAINEDTURNXXXXXXXXXXXX"
    control.add("turn.started", turn_id=drained, user_message_ids=[11])
    control.add("message.delta", turn_id=drained, delta="排队后说的话。")
    control.add("message.done", turn_id=drained)
    assert await _collect(turn) == "排队后说的话。"
    assert turn.turn_id == drained


async def test_a_merged_turn_streams_the_active_turn():
    # PRE_OUTPUT 合并：decide 给出正在跑的 turn_id；语音应挂到那一轮，而不是空流。
    control = FakeControl()
    active = "01ACTIVETURNXXXXXXXXXXXXX"

    def script(c: FakeControl) -> None:
        c.add("message.delta", turn_id=active, delta="合并后一起说。")
        c.add("message.done", turn_id=active)

    submit = FakeSubmit(control, script, disposition=Disposition.MERGED, turn_id=active)
    turn = await _brain(control, submit).start_turn(_request())
    assert await _collect(turn) == "合并后一起说。"
    assert turn.turn_id == active


async def test_a_queued_turn_ignores_other_message_drains():
    control = FakeControl()
    submit = FakeSubmit(control, lambda _c: None, disposition=Disposition.QUEUED, turn_id=None)
    turn = await _brain(control, submit).start_turn(_request())
    control.add("turn.started", turn_id="OTHER", user_message_ids=[99])
    control.add("message.delta", turn_id="OTHER", delta="别人的排队")
    control.add("message.done", turn_id="OTHER")
    mine = "01MINEDRAINEDTURNXXXXXXXX"
    control.add("turn.started", turn_id=mine, user_message_ids=[11])
    control.add("message.delta", turn_id=mine, delta="我的。")
    control.add("message.done", turn_id=mine)
    assert await _collect(turn) == "我的。"


async def test_no_session_is_a_programming_error():
    control = FakeControl()
    with pytest.raises(ValueError):
        await _brain(control, FakeSubmit(control, _happy)).start_turn(_request(session_id=None))


async def test_a_non_numeric_user_id_is_refused_before_anything_is_written():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    bad = TurnRequest(user_id="alice", character_id="linche", message="hi", session_id=SESSION)
    with pytest.raises(ValueError):
        await _brain(control, submit).start_turn(bad)
    assert submit.calls == []


async def test_stream_end_logs_which_event_closed_it_and_how_many_deltas(caplog):
    """RCA 探针（拨测 14:30 UTC）：`said=''` 但 `interrupted=False` 的回合里，
    tokens() 是被哪个结束事件关掉的、之前喂过几个 delta——没有这行就得拿时间差猜。

    生产里 `voice reply said='' interrupted=False` + `first_ms=None` 的组合意味着
    tokens() 正常耗尽：要么 END 事件前一个 delta 都没有，要么 delta 全被 turn_id 过滤。
    这行日志把两种情况钉死。
    """
    control = FakeControl()

    def script(c: FakeControl) -> None:
        c.add("turn.started", turn_id=TURN)
        c.add("message.delta", turn_id=TURN, delta="前半句。")
        c.add("turn.cancelled", turn_id=TURN)

    submit = FakeSubmit(control, script)
    turn = await _brain(control, submit).start_turn(_request())
    with caplog.at_level("INFO", logger="companion.service.turns.platform_brain"):
        assert await _collect(turn) == "前半句。"

    ends = [r.getMessage() for r in caplog.records if "voice turn stream end" in r.getMessage()]
    assert any("event=turn.cancelled" in m and "deltas=1" in m and TURN in m for m in ends)


async def test_zero_delta_end_is_visible_as_zero_delta(caplog):
    """空回复的判别式：END 到达时 deltas=0 —— token 丢在 merged 之前/之中，而不是断句。"""
    control = FakeControl()

    def script(c: FakeControl) -> None:
        c.add("turn.started", turn_id=TURN)
        c.add("message.done", turn_id=TURN)

    turn = await _brain(control, FakeSubmit(control, script)).start_turn(_request())
    with caplog.at_level("INFO", logger="companion.service.turns.platform_brain"):
        assert await _collect(turn) == ""

    ends = [r.getMessage() for r in caplog.records if "voice turn stream end" in r.getMessage()]
    assert any("event=message.done" in m and "deltas=0" in m for m in ends)


async def test_sending_cancel_is_logged(caplog):
    """打断取消要留痕：语音 barge-in 取消的是共享的文字回合，别的语音订阅者
    （merged/queued 挂在同一个 turn 上）会因此提前收流——没这行就无法对账是谁杀的。"""
    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, lambda c: c.add("turn.started", turn_id=TURN))
                        ).start_turn(_request())
    with caplog.at_level("INFO", logger="companion.service.turns.platform_brain"):
        await turn.cancel_turn()

    assert control.cancelled == [TURN]
    assert any("voice turn cancel sent" in r.getMessage() and TURN in r.getMessage()
               for r in caplog.records)


async def test_first_delta_receipt_is_logged(caplog):
    """② 段的收口探针：首句要 19–31 秒（拨测 first_ms=19143/30986）时，必须分清
    是「chat 侧把 delta 送进事件流慢」还是「voice 侧拿到 delta 后断句慢」。
    这行给 platform_brain 观察到第一个 delta 的时刻。"""
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    turn = await _brain(control, submit).start_turn(_request())
    with caplog.at_level("INFO", logger="companion.service.turns.platform_brain"):
        assert await _collect(turn) == "先歇一会儿，我在。"

    firsts = [r.getMessage() for r in caplog.records if "voice turn first delta" in r.getMessage()]
    assert any(TURN in m and "after_ms=" in m for m in firsts)


async def test_raw_delta_is_preferred_over_the_display_delta():
    """展示清洗后 delta 只剩 say；朗读必须读 raw_delta，否则 cues 再也提不出来。"""
    def script(control: FakeControl) -> None:
        control.add("turn.started", turn_id=TURN)
        control.add("message.delta", turn_id=TURN, delta="好。",
                    raw_delta='{"say":"好。","cues":[{"kind":"avatar.expression","name":"calm"}]}')
        control.add("message.done", turn_id=TURN, assistant_message_id=12)

    control = FakeControl()
    turn = await _brain(control, FakeSubmit(control, script)).start_turn(_request())
    assert await _collect(turn) == '{"say":"好。","cues":[{"kind":"avatar.expression","name":"calm"}]}'
