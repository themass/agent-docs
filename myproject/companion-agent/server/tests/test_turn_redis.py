"""回合控制面（Redis + Lua）、运行器、SSE 与会话接口的集成测试。

需要真实 Redis：设置 COMPANION_TEST_REDIS_URL 才会运行，否则跳过。
每个用例使用随机的会话 id，只删除自己创建的键，不会清空库（可以指向共享的 Redis）。
"""

import asyncio
import os
import random
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from companion.service.turn.redis_control import lock_key, turn_key

REDIS_URL = os.environ.get("COMPANION_TEST_REDIS_URL", "")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="COMPANION_TEST_REDIS_URL not set")


def _session_id() -> int:
    return random.randint(10**9, 10**10)


@pytest.fixture
async def redis_client():
    import redis.asyncio as redis

    client = redis.from_url(REDIS_URL, decode_responses=False)
    yield client
    await client.aclose()


@pytest.fixture
async def control(redis_client):
    from companion.service.turn.redis_control import RedisTurnControl

    return RedisTurnControl(redis_client)


class Messages:
    def __init__(self):
        self.rows = {}
        self.attached = {}
        self.next_id = 1000

    async def append(self, *, owner_id, session_id, role, content, kind, client_message_id, turn_id, meta,
                     fence=None, alt_of=None):
        self.alt_of_seen = alt_of
        group = None
        if alt_of is not None and alt_of in self.rows:
            group = self.rows[alt_of].alt_group or alt_of
            self.rows[alt_of].alt_group = group
        m = SimpleNamespace(id=self.next_id, owner_id=owner_id, session_id=session_id, role=role,
                            content=content, kind=kind, client_message_id=client_message_id, turn_id=turn_id,
                            created_at=datetime.now(UTC), interrupted=False, meta=dict(meta or {}),
                            alt_group=group, alt_selected=True)
        self.next_id += 1
        self.rows[m.id] = m
        return m

    async def get(self, *, owner_id, message_id):
        return self.rows.get(message_id)

    async def find_by_client_id(self, **kw):
        return None

    async def attach_turn(self, *, owner_id, session_id, message_ids, turn_id):
        for mid in message_ids:
            self.attached[mid] = turn_id
        return len(message_ids)

    async def mark_interrupted(self, **kw):
        return True


class Queue:
    def __init__(self):
        self.items = []

    async def enqueue(self, *, owner_id, session_id, message_id, client_message_id, text):
        item = SimpleNamespace(id=len(self.items) + 1, message_id=message_id, text=text, drain_attempts=0)
        self.items.append(item)
        return item


async def _cleanup(redis_client, sid):
    from companion.service.turn.redis_control import events_key, lock_key, turn_key

    await redis_client.delete(events_key(sid), turn_key(sid), lock_key(sid))


@pytest.mark.parametrize("phase,steerable,used,expected", [
    ("pre_output", True, 0, "merged"),
    ("output", True, 0, "steered"),
    ("output", True, 3, "queued"),
    ("output", False, 0, "queued"),
    ("tool", True, 0, "queued"),
])
async def test_lua_decision_matches_the_domain_table(control, redis_client, phase, steerable, used, expected):
    from companion.service.turn.queue import TurnPhase

    sid = _session_id()
    try:
        assert await control.acquire_lock(session_id=sid, owner="p:T")
        await control.init_turn(session_id=sid, turn_id="T")
        await control.advance_phase(session_id=sid, phase=TurnPhase.OUTPUT if phase == "output"
                                    else TurnPhase.TOOL if phase == "tool" else TurnPhase.PRE_OUTPUT)
        if used:
            await redis_client.hset(turn_key(sid), "steer_used", used)
        disposition, _tid = await control.decide(session_id=sid, message_id="9", text="x",
                                                 steerable=steerable, steer_budget=3, max_restarts=2)
        assert disposition.value == expected
    finally:
        await _cleanup(redis_client, sid)


async def test_phase_only_moves_forward(control, redis_client):
    from companion.service.turn.queue import TurnPhase

    sid = _session_id()
    try:
        await control.acquire_lock(session_id=sid, owner="p:T")
        await control.init_turn(session_id=sid, turn_id="T")
        assert await control.advance_phase(session_id=sid, phase=TurnPhase.OUTPUT)
        assert not await control.advance_phase(session_id=sid, phase=TurnPhase.PRE_OUTPUT)
    finally:
        await _cleanup(redis_client, sid)


async def test_lock_release_only_by_owner(control, redis_client):
    sid = _session_id()
    try:
        assert await control.acquire_lock(session_id=sid, owner="a:T1")
        assert not await control.acquire_lock(session_id=sid, owner="b:T2")
        await control.release_lock(session_id=sid, owner="b:T2")
        assert await redis_client.exists(lock_key(sid))
        await control.release_lock(session_id=sid, owner="a:T1")
        assert not await redis_client.exists(lock_key(sid))
    finally:
        await _cleanup(redis_client, sid)


async def test_merge_during_pre_output_restarts_and_attaches_the_merged_message(control, redis_client):
    from companion.service.chat.submit import SubmitService
    from companion.service.chat.turn_runner import TurnInput, TurnRunner
    from companion.service.chat.lifecycle import DrainState
    from companion.agent.brain.port import TextDelta

    sid = _session_id()
    messages, queue = Messages(), Queue()
    tasks, box = [], {}
    calls = {"n": 0}
    gate = asyncio.Event()  # 首次模型调用在合并消息入队之后才产出首 token（不依赖时间）

    async def start_turn(*, owner_id, session_id, character_id, turn_id, owner, text, message_ids):
        turn = TurnInput(owner_id=owner_id, session_id=session_id, character_id=character_id, turn_id=turn_id,
                         owner=owner, text=text, message_ids=message_ids)
        tasks.append(asyncio.create_task(box["runner"].run(turn)))

    async def produce(request, inbox):
        calls["n"] += 1
        if calls["n"] == 1:
            await gate.wait()
        yield TextDelta("回答")

    tracker = DrainState()
    box["runner"] = TurnRunner(control=control, messages=messages, queue=queue, produce=produce, tracker=tracker)
    submit = SubmitService(messages=messages, queue=queue, control=control, start_turn=start_turn,
                           process_name="test")
    try:
        first = await submit.submit(owner_id=7, session_id=sid, character_id="linche", text="第一句",
                                    client_message_id=None)
        await asyncio.sleep(0.05)
        second = await submit.submit(owner_id=7, session_id=sid, character_id="linche", text="补充",
                                     client_message_id=None)
        gate.set()
        await asyncio.gather(*tasks)
        assert first.disposition.value == "started"
        assert second.disposition.value == "merged"
        assert messages.attached[second.message_id] == first.turn_id
        assert calls["n"] == 2
        events = [name for _id, name, _data in await control.read_events_after(session_id=sid, after_id="0-0")]
        assert "turn.restarted" in events and events[-1] == "message.done"
        assert tracker.active_turns == 0
        assert not await redis_client.exists(lock_key(sid))
    finally:
        await _cleanup(redis_client, sid)


async def test_steer_during_output_is_injected_and_attached(control, redis_client):
    from companion.service.chat.submit import SubmitService
    from companion.service.chat.turn_runner import TurnInput, TurnRunner
    from companion.agent.brain.port import TextDelta

    sid = _session_id()
    messages, queue = Messages(), Queue()
    tasks, box = [], {}

    async def start_turn(*, owner_id, session_id, character_id, turn_id, owner, text, message_ids):
        turn = TurnInput(owner_id=owner_id, session_id=session_id, character_id=character_id, turn_id=turn_id,
                         owner=owner, text=text, message_ids=message_ids)
        tasks.append(asyncio.create_task(box["runner"].run(turn)))

    async def produce(request, inbox):
        yield TextDelta("先说一句")
        await asyncio.sleep(0.4)
        inbox.take_all()
        yield TextDelta("，再补充")

    box["runner"] = TurnRunner(control=control, messages=messages, queue=queue, produce=produce)
    submit = SubmitService(messages=messages, queue=queue, control=control, start_turn=start_turn,
                           process_name="test")
    try:
        first = await submit.submit(owner_id=7, session_id=sid, character_id="linche", text="问题",
                                    client_message_id=None)
        await asyncio.sleep(0.2)
        steer = await submit.submit(owner_id=7, session_id=sid, character_id="linche", text="插话",
                                    client_message_id=None)
        await asyncio.gather(*tasks)
        assert steer.disposition.value == "steered"
        assert messages.attached[steer.message_id] == first.turn_id
        assert queue.items == []
    finally:
        await _cleanup(redis_client, sid)


async def test_uninjected_steer_goes_back_to_the_queue(control, redis_client):
    from companion.service.chat.turn_runner import TurnInput, TurnRunner
    from companion.service.turn.queue import TurnPhase
    from companion.agent.brain.port import TextDelta

    sid = _session_id()
    messages, queue = Messages(), Queue()

    async def produce(request, inbox):
        yield TextDelta("只说这些")

    runner = TurnRunner(control=control, messages=messages, queue=queue, produce=produce)
    try:
        await control.acquire_lock(session_id=sid, owner="p:T")
        await control.init_turn(session_id=sid, turn_id="T")
        await control.send_cancel(turn_id="T")  # 无关的控制消息不应影响收尾
        await control.publish(session_id=sid, event="noop", data={})
        from companion.service.chat.turn_runner import _RunState
        inp = TurnInput(owner_id=7, session_id=sid, character_id="linche", turn_id="T", owner="p:T",
                        text="x", message_ids=[1])
        state = _RunState()
        state.steer_pushed.append(55)
        from companion.agent.brain.steer import SteerInbox
        inbox = SteerInbox(budget=3)
        inbox.push("55", "没来得及注入")
        await runner._finish(inp, state, inbox)
        assert [item.text for item in queue.items] == ["没来得及注入"]
        assert 55 not in messages.attached
    finally:
        await _cleanup(redis_client, sid)


async def test_sse_snapshot_resume_gone_reconnect_and_keepalive(control, redis_client):
    from companion.api.sse.stream import event_stream

    sid = _session_id()
    try:
        await control.publish(session_id=sid, event="message.created", data={"message_id": 1})
        assert await control.acquire_lock(session_id=sid, owner="p:TS")
        await control.init_turn(session_id=sid, turn_id="TS", message_ids=[1, 2])
        await control.append_text(turn_id="TS", delta="已经说到这里")
        await control.publish(session_id=sid, event="message.delta", data={"turn_id": "TS", "delta": "x"})
        first = (await control.read_events_after(session_id=sid, after_id="0-0"))[0][0]

        async def take(gen, n):
            out = []
            async for frame in gen:
                out.append(frame)
                if len(out) >= n:
                    break
            return out

        fresh = await take(event_stream(control=control, session_id=sid, last_event_id=None,
                                        draining=lambda: False, keepalive_sec=0.2), 1)
        assert "event: turn.snapshot" in fresh[0] and "已经说到这里" in fresh[0] and '"user_message_ids":[1,2]' in fresh[0]

        resumed = await take(event_stream(control=control, session_id=sid, last_event_id=first,
                                          draining=lambda: False, keepalive_sec=0.2), 1)
        assert "event: message.delta" in resumed[0]

        gone = await take(event_stream(control=control, session_id=sid, last_event_id="1-0",
                                       draining=lambda: False), 1)
        assert "event: gone" in gone[0]

        reconnect = await take(event_stream(control=control, session_id=sid, last_event_id=first,
                                            draining=lambda: True), 1)
        assert "event: reconnect" in reconnect[0]

        idle = await take(event_stream(control=control, session_id=sid, last_event_id="99999999999999-0",
                                       draining=lambda: False, keepalive_sec=0.2), 1)
        assert idle[0] == ": keepalive\n\n"
    finally:
        await _cleanup(redis_client, sid)


async def test_merge_that_lands_before_the_first_token_is_never_lost(control, redis_client):
    """回归测试：合并消息在首 token 之前已进入控制流，但后台协程还没读到。

    Lua 判定为合并后、运行器读到之前，首 token 就到了。修复前这条合并会被丢掉。
    """
    from companion.service.chat.turn_runner import TurnInput, TurnRunner
    from companion.agent.brain.port import TextDelta
    from companion.service.turn.redis_control import ctl_key

    sid = _session_id()
    messages, queue = Messages(), Queue()
    calls = {"n": 0}

    async def produce(request, inbox):
        calls["n"] += 1
        yield TextDelta("回答")  # 首 token 立即到达

    runner = TurnRunner(control=control, messages=messages, queue=queue, produce=produce)
    try:
        assert await control.acquire_lock(session_id=sid, owner="p:RACE")
        await control.init_turn(session_id=sid, turn_id="RACE", message_ids=[1])
        # 模拟 Lua 在 pre_output 阶段写入的合并控制消息（运行器尚未读取）
        await redis_client.xadd(ctl_key("RACE"), {"kind": "merge", "message_id": "77", "text": "补充一句"})
        inp = TurnInput(owner_id=7, session_id=sid, character_id="linche", turn_id="RACE", owner="p:RACE",
                        text="第一句", message_ids=[1])
        await runner.run(inp)
        assert calls["n"] == 2  # 首次被合并中止，重跑一次
        assert messages.attached.get(77) == "RACE"
        assert any(m.role == "assistant" and m.content == "回答" for m in messages.rows.values())
        events = [name for _id, name, _data in await control.read_events_after(session_id=sid, after_id="0-0")]
        assert "turn.restarted" in events
    finally:
        await _cleanup(redis_client, sid)
