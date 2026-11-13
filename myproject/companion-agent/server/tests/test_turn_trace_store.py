"""回合追踪的存储：写入、还原、去重、重跑合并、同意、清理不误删、按用户隔离。内存 SQLite。"""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from companion.adapters.store.sql.qa import SqlQaStore
from companion.adapters.store.sql.schema import text_blob, turn_trace
from companion.domain.trace.model import LlmCall

SYSTEM = "你是林澈。\n\n说话简短。\n\n" + "\n\n".join(f"规则{i}：" + "x" * 60 for i in range(20))


def call(seq=0, messages=None, **kw) -> LlmCall:
    base = dict(seq=seq, model="m", input_messages=messages or [{"role": "system", "content": SYSTEM},
                                                                {"role": "human", "content": "今天好累"}],
                output_text="先歇一会儿", input_tokens=50, output_tokens=6, total_ms=300)
    base.update(kw)
    return LlmCall(**base)


async def write(store, turn="T1", owner=1002, calls=None, keep=True):
    return await store.record_trace(turn_id=turn, session_id=7, owner_id=owner, role_id="linche",
                                    calls=calls or [call()], keep_content=keep)


async def blobs(engine, owner=None):
    async with engine.connect() as conn:
        q = select(text_blob)
        if owner is not None:
            q = q.where(text_blob.c.owner_id == owner)
        return (await conn.execute(q)).mappings().all()


async def test_a_turn_is_stored_in_one_row_and_read_back_exactly(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    first = call(0, tool_calls=[{"id": "c1", "name": "add_event", "args": {"title": "面试"}}])
    asked = {"role": "ai", "content": "", "tool_calls": [{"id": "c1", "name": "add_event"}]}
    second = call(1, first.input_messages + [asked, {"role": "tool", "content": "已添加", "tool_call_id": "c1", "name": "add_event"}],
                  output_text="记下了")
    await write(store, calls=[first, second])

    async with sqlite_engine.connect() as conn:
        rows = (await conn.execute(select(turn_trace))).mappings().all()
    assert len(rows) == 1                                           # 一个回合一行，不是一次调用一行
    t = await store.read_trace(turn_id="T1")
    assert [s["seq"] for s in t["steps"]] == [0, 1]
    assert [m["content"] for m in t["steps"][0]["input"]] == [m["content"] for m in first.input_messages]
    assert t["steps"][1]["input"][-1]["tool_call_id"] == "c1" and t["steps"][1]["input"][-1]["content"] == "已添加"
    assert t["steps"][1]["output"] == "记下了" and t["steps"][0]["tools"][0]["args"] == {"title": "面试"}
    assert t["usage"] == {"calls": 2, "input_tokens": 100, "output_tokens": 12, "cached_tokens": 0, "llm_ms": 600, "tool_calls": 1}
    assert t["content_kept"] is True


async def test_the_same_text_is_stored_once_across_turns(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, "T1")
    n1 = len(await blobs(sqlite_engine))
    await write(store, "T2", calls=[call(messages=[{"role": "system", "content": SYSTEM + "\n\n【记得的】新增"},
                                                    {"role": "human", "content": "第二句"}])])
    n2 = len(await blobs(sqlite_engine))
    assert n1 >= 20 and n2 - n1 == 2                                # 角色卡和规则全复用，只新增变化的两段
    assert (await store.read_trace(turn_id="T2"))["steps"][0]["input"][0]["content"].endswith("【记得的】新增")


async def test_without_consent_no_text_reaches_the_database_at_all(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, keep=False, calls=[call(tool_calls=[{"id": "c", "name": "add_event", "args": {"title": "周五面试"}}])])

    assert await blobs(sqlite_engine) == []
    async with sqlite_engine.connect() as conn:
        raw = json.dumps((await conn.execute(select(turn_trace.c.steps))).scalar_one(), ensure_ascii=False)
    assert "今天好累" not in raw and "先歇一会儿" not in raw and "周五面试" not in raw and "你是林澈" not in raw
    t = await store.read_trace(turn_id="T1")
    assert t["content_kept"] is False and t["usage"]["input_tokens"] == 50
    assert t["steps"][0]["tools"] == [{"id": "c", "name": "add_event"}]


async def test_a_restarted_turn_appends_instead_of_overwriting_and_usage_adds_up(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, calls=[call(0, input_tokens=100, output_text="第一次的半截")])
    merged = await write(store, calls=[call(0, input_tokens=120, output_text="重跑后的完整回答")])

    assert len(merged) == 2 and [s["a"] for s in merged] == [0, 1]
    t = await store.read_trace(turn_id="T1")
    assert t["attempts"] == 2 and [s["output"] for s in t["steps"]] == ["第一次的半截", "重跑后的完整回答"]
    assert t["usage"]["input_tokens"] == 220 and t["usage"]["calls"] == 2
    assert "base" in json.dumps(merged) and t["steps"][1]["input"][1]["content"] == "今天好累"      # 第二次尝试自带完整输入


async def test_a_later_attempt_with_consent_marks_the_row_as_holding_content(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, keep=False)
    await write(store, keep=True)
    assert (await store.read_trace(turn_id="T1"))["content_kept"] is True


async def test_a_trace_of_another_user_is_not_readable_with_my_id(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, "T1", owner=1002)
    assert await store.read_trace(turn_id="T1", owner_id=1003) is None
    assert await store.read_trace(turn_id="T1", owner_id=1002) is not None


async def test_identical_text_of_two_users_is_stored_per_user(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, "T1", owner=1002)
    await write(store, "T2", owner=1003)
    assert len(await blobs(sqlite_engine, 1002)) == len(await blobs(sqlite_engine, 1003)) > 0
    await store.delete_user(owner_id=1002)
    assert await blobs(sqlite_engine, 1002) == [] and len(await blobs(sqlite_engine, 1003)) > 0
    assert await store.read_trace(turn_id="T2", owner_id=1003) is not None        # 另一个人的内容完整无损


async def _age(engine, table, days, column, where=None):
    q = update(table).values(**{column: datetime.now(UTC) - timedelta(days=days)})
    async with engine.begin() as conn:
        await conn.execute(q.where(where) if where is not None else q)


async def test_purge_never_removes_a_block_that_an_unexpired_trace_still_uses(sqlite_engine):
    """最容易出错的一处：角色卡在第 1 天第一次存下，第 100 天仍被新回合引用。按“第一次存的时间”清就会把它清掉。"""
    store = SqlQaStore(sqlite_engine)
    await write(store, "OLD")
    await _age(sqlite_engine, turn_trace, 100, "created_at")
    await _age(sqlite_engine, text_blob, 100, "last_seen_at")
    await write(store, "NEW")                                               # 新回合再次引用同样的角色卡 → 刷新 last_seen_at

    await store.purge_before(cutoff=datetime.now(UTC) - timedelta(days=90))

    assert await store.read_trace(turn_id="OLD") is None
    t = await store.read_trace(turn_id="NEW")
    assert "缺失文本块" not in json.dumps(t, ensure_ascii=False, default=str)
    assert t["steps"][0]["input"][0]["content"] == SYSTEM


async def test_purge_removes_blocks_nothing_references_any_more(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store, "OLD")
    await _age(sqlite_engine, turn_trace, 100, "created_at")
    await _age(sqlite_engine, text_blob, 100, "last_seen_at")
    await store.purge_before(cutoff=datetime.now(UTC) - timedelta(days=90))
    assert await blobs(sqlite_engine) == []


async def test_more_blocks_than_one_insert_batch_are_all_written(sqlite_engine):
    from companion.adapters.store.sql.qa import BLOB_BATCH

    store = SqlQaStore(sqlite_engine)
    n = BLOB_BATCH * 2 + 37
    # 每条消息都短，不触发单条上限的截断；块数超过一批，才真的走到分批写入
    msgs = [{"role": "human", "content": f"第{i}条：" + "字" * 20} for i in range(n)]
    await write(store, calls=[call(messages=msgs)])
    # 块 = 全部输入各一块 + 这次调用的输出一块（输出也按内容存）
    assert {b["body"] for b in await blobs(sqlite_engine)} == {m["content"] for m in msgs} | {"先歇一会儿"}
    got = (await store.read_trace(turn_id="T1"))["steps"][0]["input"]
    assert [m["content"] for m in got] == [m["content"] for m in msgs]


async def test_a_missing_block_shows_up_as_missing_not_as_empty(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    await write(store)
    async with sqlite_engine.begin() as conn:
        from sqlalchemy import delete
        await conn.execute(delete(text_blob))
    t = await store.read_trace(turn_id="T1")
    assert "缺失文本块" in t["steps"][0]["input"][0]["content"]


async def test_reading_an_unknown_turn_gives_none(sqlite_engine):
    assert await SqlQaStore(sqlite_engine).read_trace(turn_id="nope") is None


async def test_no_calls_writes_nothing(sqlite_engine):
    store = SqlQaStore(sqlite_engine)
    assert await store.record_trace(turn_id="T", session_id=1, owner_id=1, role_id="r", calls=[], keep_content=True) == []
    assert (await store.count())["turn_trace"] == 0
