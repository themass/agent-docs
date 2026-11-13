"""账号注销的跨存储删除（chat-agent-ops-design.md §3）。

关系库部分需要 COMPANION_TEST_DATABASE_URL；控制面、线程、对象存储用假实现记下调用。
每个用例用随机 owner_id，不清别人的数据。
"""

import os
import random
from datetime import UTC, datetime, timedelta

import pytest

from companion.adapters.store.sql.account import SqlAccountStore
from companion.adapters.store.sql.jobs import SqlJobStore
from companion.memory.sql import SqlMemoryPort
from companion.adapters.store.sql.reminders import SqlReminderStore
from companion.adapters.store.sql.repositories import SqlMessageStore, SqlRoleStore, SqlSessionStore
from companion.timeline.memory import InMemoryTimeline
from companion.app.account.purge import PURGE_JOB, AccountPurgeService
from companion.app.jobs.handlers import memory_record
from companion.memory.subject import role_subject
from companion.timeline.models import EventKind, TimelineEvent
from companion.memory.port import MemoryItem
from memory_hub import AppConfig, MemoryHub

URL = os.environ.get("COMPANION_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")


class Recorder:
    def __init__(self):
        self.calls = []

    async def purge_session(self, *, session_id):
        self.calls.append(("redis", session_id))

    async def delete_threads(self, *, session_ids):
        self.calls.append(("threads", tuple(session_ids)))

    async def delete(self, *, key):
        self.calls.append(("object", key))


@pytest.fixture
async def engine(memory_schema):
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(URL, pool_pre_ping=True)
    yield eng
    await eng.dispose()


async def _seed(engine, owner):
    sessions = SqlSessionStore(engine)
    messages = SqlMessageStore(engine)
    s1 = await sessions.create(owner_id=owner, role_id="linche", name="", locale="zh-CN")
    s2 = await sessions.create(owner_id=owner, role_id="sudai", name="", locale="zh-CN")
    for s in (s1, s2):
        await messages.append(owner_id=owner, session_id=s.id, role="user", content="你好", kind="text",
                              client_message_id=None, turn_id=None, meta={})
    await SqlRoleStore(engine).create(owner_id=owner, public_id=f"u{owner}r", name="自建", tagline="",
                                      description="d", prompt="p", locale="zh-CN")
    await SqlReminderStore(engine).create(owner_id=owner, session_id=s1.id, role_id="linche",
                                          due_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
                                          timezone="Asia/Shanghai", content="开会", confirmation_id=None)
    return s1, s2


async def test_purge_removes_everything_and_is_repeatable(engine):
    owner, other = random.randint(10**8, 10**9), random.randint(10**9, 2 * 10**9)
    s1, s2 = await _seed(engine, owner)
    keep, _ = await _seed(engine, other)

    memory = MemoryHub.from_config([AppConfig("companion")], lambda cfg: SqlMemoryPort(engine)).for_app("companion")
    await memory.add(role_subject(owner, "linche"), [MemoryItem(id="", content="喜欢喝茶")])
    await memory.add(role_subject(owner, "sudai"), [MemoryItem(id="", content="喜欢咖啡")])
    await memory.add(role_subject(owner, "catalog-role"), [MemoryItem(id="", content="只在目录角色里说过")])
    await memory.add(str(owner), [MemoryItem(id="", content="手动加的")])
    await memory.add(role_subject(other, "linche"), [MemoryItem(id="", content="别人的")])
    timeline = InMemoryTimeline()
    await timeline.add(TimelineEvent(id=f"e{owner}", user_id=str(owner), kind=EventKind.OTHER, title="面试",
                                     at=datetime.now(UTC) + timedelta(days=2)))
    jobs = SqlJobStore(engine)
    await jobs.enqueue(kind="memory.record", payload={"owner_id": owner, "session_id": s1.id, "turn_id": "t"},
                       run_after=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
                       dedupe_key=f"memory.record:t{owner}")
    fakes = Recorder()
    service = AccountPurgeService(store=SqlAccountStore(engine), jobs=jobs, control=fakes, threads=fakes,
                                  memory=memory, timeline=timeline, objects=fakes,
                                  system_roles=lambda: ("catalog-role",))

    await service.request(owner_id=owner)
    assert await SqlSessionStore(engine).get(owner_id=owner, session_id=s1.id) is None   # 立即关闭

    report = await service.run(owner_id=owner)
    assert report.sessions == 2 and report.memories == 4 and report.events == 1
    assert ("threads", tuple(sorted((s1.id, s2.id)))) in fakes.calls
    assert {("redis", s1.id), ("redis", s2.id)} <= set(fakes.calls)

    footprint = await SqlAccountStore(engine).footprint(owner_id=owner)
    assert footprint.session_ids == () and footprint.role_ids == ()
    for subject in (role_subject(owner, "linche"), role_subject(owner, "catalog-role"), str(owner)):
        assert await memory.list_for_user(subject) == []
    assert await memory.list_for_user(role_subject(other, "linche")) != []
    assert await SqlSessionStore(engine).get(owner_id=other, session_id=keep.id) is not None

    from sqlalchemy import func, select

    from companion.adapters.store.sql.schema import account_purge_log, agent_job

    async with engine.connect() as conn:
        pending = (await conn.execute(select(agent_job.c.payload).where(
            agent_job.c.dedupe_key == f"memory.record:t{owner}"))).first()
        logs = (await conn.execute(select(func.count()).select_from(account_purge_log))).scalar()
    assert pending is None and logs >= 1

    again = await service.run(owner_id=owner)   # 重试无副作用
    assert again.rows == 0 and again.memories == 0

    from companion.app.account.purge import user_hash

    async with engine.begin() as conn:
        await conn.execute(agent_job.delete().where(
            agent_job.c.dedupe_key == f"{PURGE_JOB}:{user_hash(owner)[:32]}"))


async def test_memory_job_for_closed_session_is_skipped(engine):
    owner = random.randint(10**8, 10**9)
    s1, _ = await _seed(engine, owner)
    await SqlAccountStore(engine).close_sessions(owner_id=owner)
    recorded = []

    class Pipeline:
        async def record(self, turn):
            recorded.append(turn)

    handle = memory_record(Pipeline(), sessions=SqlSessionStore(engine))
    await handle({"owner_id": owner, "session_id": s1.id, "turn_id": "x", "user_text": "我养猫"})
    assert recorded == []
    await SqlAccountStore(engine).purge(owner_id=owner)


@pytest.mark.skipif(not os.environ.get("COMPANION_TEST_REDIS_URL"), reason="COMPANION_TEST_REDIS_URL not set")
async def test_redis_purge_session_cancels_and_clears():
    from redis import asyncio as redis_async

    from companion.adapters.cache.redis.control import (
        RedisTurnControl,
        ctl_key,
        events_key,
        fence_key,
        lock_key,
        turn_key,
    )

    r = redis_async.from_url(os.environ["COMPANION_TEST_REDIS_URL"])
    control = RedisTurnControl(r)
    sid = random.randint(10**8, 10**9)
    try:
        await control.acquire_lock(session_id=sid, owner="p")
        await control.next_fence(session_id=sid)
        await control.init_turn(session_id=sid, turn_id=f"T{sid}")
        await control.publish(session_id=sid, event="delta", data={"text": "x"})
        await control.purge_session(session_id=sid)
        for key in (turn_key(sid), lock_key(sid), fence_key(sid), events_key(sid), ctl_key(f"T{sid}")):
            assert not await r.exists(key)
        await control.purge_session(session_id=sid)   # 重复执行无副作用
    finally:
        await r.aclose()
