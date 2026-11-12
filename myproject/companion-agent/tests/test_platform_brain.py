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

from companion.domain.turn.queue import Disposition
from companion.ports.brain import TurnRequest

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
    from companion.adapters.brain.platform_brain import PlatformBrain

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
    from companion.adapters.brain.platform_brain import TurnRefused

    control = FakeControl()
    with pytest.raises(TurnRefused) as info:
        await _brain(control, FakeSubmit(control, _happy, status="denied", disposition=None, turn_id=None)
                     ).start_turn(_request())
    assert info.value.reason == "blocked"


async def test_a_queued_turn_has_nothing_to_stream():
    # 会话正忙（比如文字那边正在回复）：这句话已经落库排队，由当前回合结束后的 drain 处理，
    # 语音这边不挂等一个还没开始的回合。
    control = FakeControl()
    submit = FakeSubmit(control, _happy, disposition=Disposition.QUEUED, turn_id=None)
    turn = await _brain(control, submit).start_turn(_request())
    assert await _collect(turn) == ""


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
