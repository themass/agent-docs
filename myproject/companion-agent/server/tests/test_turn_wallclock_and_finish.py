"""回合级 wall-clock 兜底 + 收尾尽力而为（2026-11-28 生产挂死）。

两个钉子：

1. **回合永不终结**：``TurnRunner._run/_attempt`` 没有任何总时长闸。brain 流或工具
   的某个 await 挂死后，持锁的回合任务永远不返回，续租还一直把锁续活——终止事件
   永远发不出去，锁永远不放。修法是给 ``_run`` 的模型+工具阶段套 ``asyncio.timeout``，
   到点走 ``error{code:"turn_timeout"}`` 收尾；收尾本身在超时闸**之外**（finally），
   续租任务在收尾前必须停掉。

2. **``_finish`` 抛错吞终止事件**：``finally: await self._finish(...)`` 没有保护，
   ``_finish`` 里任何一步（flush / DB append / attach_turn）抛错 → 终止事件和放锁
   一起丢。修法：收尾失败走紧急路径——终止事件与 ``release_lock`` 各自独立尝试。

不需要真 Redis/DB：全部用记录型假件，模式沿用 ``test_turn_control_roundtrips.py`` /
``test_turn_redis.py`` 的 fakes（去掉真库依赖）。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from companion.service.chat import turn_runner as tr
from companion.service.chat.turn_runner import TurnInput, TurnRunner
from companion.agent.brain.port import BrainEvent, TextDelta


class FakeControl:
    def __init__(self, *, fail_publish: bool = False, fail_finish_turn: bool = False) -> None:
        self.published: list[tuple[str, dict]] = []
        self.finished: list[tuple[str, dict]] = []
        self.released: list[str] = []
        self.renews = 0
        self._fail_publish = fail_publish
        self._fail_finish_turn = fail_finish_turn

    async def publish(self, *, session_id: int, event: str, data: dict) -> str:
        if self._fail_publish:
            raise RuntimeError("redis publish down")
        self.published.append((event, data))
        return "1-1"

    async def publish_and_append(self, *, session_id: int, turn_id: str, event: str,
                                 data: dict, delta: str) -> str:
        if self._fail_publish:
            raise RuntimeError("redis publish down")
        self.published.append((event, data))
        return "1-1"

    async def read_ctl_after(self, *, turn_id: str, last_id: str) -> list:
        return []

    async def read_ctl(self, *, turn_id: str, last_id: str, block_ms: int = 1000) -> list:
        await asyncio.sleep(0.02)   # 模拟阻塞读，不许真等 block_ms
        return []

    async def advance_phase(self, *, session_id: int, phase) -> bool:
        return True

    async def set_phase(self, *, session_id: int, phase) -> None:
        return None

    async def renew_lock(self, *, session_id: int, owner: str) -> bool:
        self.renews += 1
        return True

    async def finish_turn(self, *, session_id: int, owner: str, turn_id: str, event: str,
                          data: dict) -> None:
        if self._fail_finish_turn:
            raise RuntimeError("redis finish_turn down")
        self.finished.append((event, data))
        self.released.append(owner)   # finish_turn 的 pipeline 里含放锁

    async def release_lock(self, *, session_id: int, owner: str) -> None:
        self.released.append(owner)

    def terminal_events(self) -> list[tuple[str, dict]]:
        """SSE 能看到的、标志回合结束的事件。"""
        return list(self.published) + list(self.finished)


class FakeMessages:
    def __init__(self, *, fail_append: bool = False) -> None:
        self.fail_append = fail_append
        self.appended: list[dict] = []
        self.attached: list[list[int]] = []
        self.next_id = 1000

    async def get(self, *, owner_id: int, message_id: int):
        return SimpleNamespace(content="在吗", meta={}, kind="chat")

    async def append(self, **kw):
        if self.fail_append:
            raise RuntimeError("db append down")
        self.appended.append(kw)
        return SimpleNamespace(id=self.next_id, alt_group=None)

    async def attach_turn(self, *, owner_id: int, session_id: int, message_ids: list[int],
                          turn_id: str) -> int:
        self.attached.append(list(message_ids))
        return len(message_ids)

    async def mark_interrupted(self, *, owner_id: int, message_id: int) -> bool:
        return True


class FakeQueue:
    async def enqueue(self, *, owner_id: int, session_id: int, message_id: int,
                      client_message_id: str | None, text: str):
        return SimpleNamespace(id=1)


def _inp() -> TurnInput:
    return TurnInput(owner_id=7, session_id=101, character_id="linche", turn_id="T1",
                     owner="proc:T1", text="在吗", message_ids=[11])


def _runner(control: FakeControl, messages: FakeMessages, produce) -> TurnRunner:
    return TurnRunner(control=control, messages=messages, queue=FakeQueue(), produce=produce)


# ------------------------------------------------- 1. wall-clock 兜底 ----


async def test_hanging_brain_stream_gets_terminal_event_and_lock_release(monkeypatch):
    """卡死的 brain 流：到点必须发终止事件、放锁，``run`` 正常返回而不是永远挂着。

    这是「回合永不终结」的直接回归：以前 produce 卡在 ``Event().wait()`` 上，
    ``_attempt`` 的 async-for 永远不返回，续租把锁续活，锁与 SSE 双双挂死。
    """
    gate = asyncio.Event()

    async def produce(request, inbox):
        yield TextDelta(text="说到一半")
        await gate.wait()          # 永不返回的 brain 流

    monkeypatch.setattr(tr, "TURN_WALL_CLOCK_SEC", 0.3)
    monkeypatch.setattr(tr, "LOCK_RENEW_SEC", 0.05)

    control, messages = FakeControl(), FakeMessages()
    runner = _runner(control, messages, produce)

    await asyncio.wait_for(runner.run(_inp()), timeout=5)   # run 必须自己结束

    errors = [d for e, d in control.published if e == "error"]
    assert any(d.get("code") == "turn_timeout" for d in errors), \
        f"没有发 turn_timeout 终止事件: {control.terminal_events()}"
    assert control.released, "锁必须释放"

    # 续租必须在超时收尾时停下来：否则一把没人认领的锁会被无限续活。
    frozen = control.renews
    await asyncio.sleep(0.15)      # 0.05s 的续租周期至少能再跳 3 次
    assert control.renews == frozen, "收尾后续租仍在跑"


async def test_wall_clock_covers_hanging_tool_phase(monkeypatch):
    """工具阶段挂死同样被闸住（挂点在 ToolStarted 之后、下一个事件之前）。"""
    gate = asyncio.Event()

    async def produce(request, inbox):
        from companion.agent.brain.port import ToolStarted

        yield ToolStarted(call_id="c1", name="hang")
        await gate.wait()

    monkeypatch.setattr(tr, "TURN_WALL_CLOCK_SEC", 0.3)
    control = FakeControl()
    runner = _runner(control, FakeMessages(), produce)

    await asyncio.wait_for(runner.run(_inp()), timeout=5)
    assert control.released


async def test_normal_turn_is_not_cut_off_by_the_wall_clock():
    """闸必须足够宽：正常（快）回合不误伤，走的还是 message.done。"""
    async def produce(request, inbox):
        yield TextDelta(text="一切正常。")

    control = FakeControl()
    runner = _runner(control, FakeMessages(), produce)
    await runner.run(_inp())

    assert not [d for e, d in control.published if e == "error"]
    assert control.finished and control.finished[-1][0] == "message.done"


async def test_wall_clock_constant_has_a_documented_bounded_value():
    """常数取值纪律：远大于正常回合，远小于「挂死也能接受」。"""
    assert 60 <= tr.TURN_WALL_CLOCK_SEC <= 600


# ------------------------------------- 2. _finish 抛错不许吞终止事件 ----


async def test_db_append_failure_still_releases_lock_and_terminates_sse():
    """``_finish`` 里 DB append 抛错：锁仍释放、SSE 仍有终止事件。

    旧行为：``finally: await self._finish(...)`` 无保护，append 一抛，终止事件与
    放锁一起丢——这正是生产挂死里「锁在、事件没有」的形态之一。
    """
    async def produce(request, inbox):
        yield TextDelta(text="写了一半的话。")

    control = FakeControl()
    messages = FakeMessages(fail_append=True)
    runner = _runner(control, messages, produce)

    await runner.run(_inp())   # 不许把异常抛穿出去

    assert control.released, "append 抛错后锁必须仍然释放"
    terminals = control.terminal_events()
    assert terminals, "SSE 必须收到至少一个终止事件"
    errors = [d for e, d in terminals if e == "error"]
    assert errors, f"消息没落库就不该报完成，应发 error 收尾: {terminals}"
    assert any(d.get("retryable") for d in errors)


async def test_attach_turn_failure_still_terminates():
    """attach_turn（挂接插话消息）抛错同样不许吃掉收尾。"""
    async def produce(request, inbox):
        yield TextDelta(text="正常回答。")

    class AttachFails(FakeMessages):
        async def attach_turn(self, **kw):
            raise RuntimeError("db attach down")

    control = FakeControl()
    runner = _runner(control, AttachFails(), produce)
    await runner.run(_inp())

    assert control.released
    assert control.terminal_events()


async def test_finish_turn_failure_falls_back_to_publish_and_release():
    """finish_turn（事件+放锁一次往返）本身抛错：紧急路径分别试 publish 与 release_lock。"""
    async def produce(request, inbox):
        yield TextDelta(text="回答。")

    control = FakeControl(fail_finish_turn=True)
    runner = _runner(control, FakeMessages(), produce)
    await runner.run(_inp())

    assert control.released, "finish_turn 失败后必须单独尝试 release_lock"
    errors = [d for e, d in control.published if e == "error"]
    assert errors, "finish_turn 失败后必须单独尝试发终止事件"


async def test_publish_failure_still_releases_lock():
    """终止事件发不出去（Redis 断）也不能拖累放锁：两件事各自独立尽力。"""
    async def produce(request, inbox):
        yield TextDelta(text="回答。")

    control = FakeControl(fail_publish=True)
    runner = _runner(control, FakeMessages(), produce)
    await runner.run(_inp())

    assert control.released
