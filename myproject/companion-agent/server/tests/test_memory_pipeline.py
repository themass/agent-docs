"""记忆编排：扇出、超时隔离、去重、排序、预算、渲染，以及写入失败不外抛。"""

import asyncio
from datetime import datetime

from companion.agent.memory.hooks import RecallQuery, RecallResult, RecalledItem, RecordOutcome, TurnRecord
from companion.agent.memory.pipeline import MemoryPipeline, render_memory_block


class Static:
    def __init__(self, name, items, delay=0.0, boom=False):
        self.name, self._items, self._delay, self._boom = name, items, delay, boom

    async def recall(self, query):
        await asyncio.sleep(self._delay)
        if self._boom:
            raise RuntimeError("down")
        return RecallResult(source=self.name, items=tuple(self._items))


def _item(text, source="facts", ref=None, at=None, score=None, tags=("fact",)):
    return RecalledItem(text=text, source=source, ref=ref or text, occurred_at=at, score=score, tags=frozenset(tags))


async def test_slow_and_failing_sources_do_not_block_the_others():
    pipe = MemoryPipeline(recallers=[
        Static("facts", [_item("喜欢茶")]),
        Static("slow", [_item("不会出现", source="slow")], delay=1.0),
        Static("broken", [], boom=True),
    ], timeout_sec=0.1)
    items, stats = await pipe.recall(RecallQuery(user_id="1", scope="companion", text="茶"))
    assert [i.text for i in items] == ["喜欢茶"]
    assert stats.per_source["slow"]["error"] == "timeout" and stats.per_source["broken"]["error"] == "RuntimeError"


async def test_dedupe_sort_by_time_then_score_and_budget():
    old, new = datetime(2026, 1, 1), datetime(2026, 6, 1)
    pipe = MemoryPipeline(recallers=[
        Static("facts", [_item("A", at=old, score=0.9), _item("B", at=new, score=0.1), _item("A", at=old)]),
        Static("timeline", [_item("C", source="timeline", score=0.99, tags=("event",))]),
    ])
    items, _ = await pipe.recall(RecallQuery(user_id="1", scope="s", text="x", budget_chars=2))
    assert [i.text for i in items] == ["B", "A"]   # 有时间的在前、新的在前；无时间的排后；预算截断


def test_render_groups_by_tag():
    block = render_memory_block([_item("喜欢茶"), _item("周三面试", source="timeline", tags=("event",))])
    assert block.index("关于用户") < block.index("喜欢茶") < block.index("近期事件") < block.index("周三面试")
    assert render_memory_block([]) == ""


async def test_recorder_failure_is_reported_not_raised():
    class Broken:
        name = "facts"

        async def record(self, turn):
            raise ValueError("bad")

    class Ok:
        name = "ok"

        async def record(self, turn):
            return RecordOutcome(source="ok", written=1)

    outcomes = await MemoryPipeline(recorders=[Broken(), Ok()]).record(TurnRecord(
        scope="s", user_id="1", turn_id="t", user_text="hi", assistant_text="", occurred_at=datetime(2026, 1, 1)))
    assert [(o.source, o.error, o.written) for o in outcomes] == [("facts", "ValueError", 0), ("ok", None, 1)]
