"""历史操作：编辑、删除、重新生成时消息表与对话线程保持一致。"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from companion.app.chat.history import (
    HistoryBusy,
    HistoryService,
    NotEditable,
    lc_ids_of,
)
from companion.domain.history.summary import RESUMMARIZE_JOB


def _msg(mid, role="user", meta=None, kind="chat", session_id=5, alt_group=None, alt_selected=True):
    return SimpleNamespace(id=mid, session_id=session_id, owner_id=1, role=role, content=f"c{mid}", kind=kind,
                           meta=meta or {}, created_at=datetime.now(UTC), interrupted=False, turn_id=None,
                           client_message_id=None, alt_group=alt_group, alt_selected=alt_selected)


class Messages:
    def __init__(self, rows):
        self.rows = {r.id: r for r in rows}
        self.deleted = set()

    async def get(self, *, owner_id, message_id):
        m = self.rows.get(message_id)
        return None if m is None or message_id in self.deleted else m

    async def soft_delete(self, *, owner_id, message_id):
        if message_id in self.deleted or message_id not in self.rows:
            return False
        self.deleted.add(message_id)
        return True

    async def edit(self, *, owner_id, message_id, content):
        self.rows[message_id].content = content
        return True

    async def list_after(self, *, owner_id, session_id, after_id, limit):
        return [m for i, m in sorted(self.rows.items())
                if i > after_id and i not in self.deleted and m.alt_selected][:limit]

    async def alternatives(self, *, owner_id, session_id, alt_group):
        return [m for i, m in sorted(self.rows.items()) if m.alt_group == alt_group and i not in self.deleted]

    async def select_alternative(self, *, owner_id, session_id, alt_group, message_id):
        group = [m for m in self.rows.values() if m.alt_group == alt_group and m.id not in self.deleted]
        if message_id not in {m.id for m in group}:
            return False
        for m in group:
            m.alt_selected = m.id == message_id
        return True


class Conversation:
    def __init__(self, ids):
        self.ids = list(ids)
        self.texts = {}
        self.appended = []

    async def remove(self, *, session_id, ids):
        hit = [i for i in ids if i in self.ids]
        self.ids = [i for i in self.ids if i not in hit]
        return len(hit)

    async def replace_user_text(self, *, session_id, lc_id, text):
        if lc_id not in self.ids:
            return False
        self.texts[lc_id] = text
        return True

    async def append_assistant(self, *, session_id, lc_id, text):
        self.appended.append((lc_id, text))


class Control:
    def __init__(self, free=True):
        self.free = free
        self.released = []

    async def acquire_lock(self, *, session_id, owner):
        return self.free

    async def release_lock(self, *, session_id, owner):
        self.released.append(owner)


class Jobs:
    def __init__(self):
        self.items = []

    async def enqueue(self, *, kind, payload, run_after, dedupe_key=None, max_attempts=5):
        self.items.append((kind, payload))
        return True


def _service(rows, ids, free=True):
    msgs, conv, ctl, jobs = Messages(rows), Conversation(ids), Control(free), Jobs()
    return HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs), msgs, conv, ctl, jobs


def test_lc_ids_cover_user_assistant_and_interrupted_note():
    assert lc_ids_of(_msg(3)) == ["m3"]
    assert lc_ids_of(_msg(4, role="system", kind="proactive")) == ["m4"]
    assert lc_ids_of(_msg(5, role="assistant", meta={"lc_ids": ["run-1", "tool-1"]})) == ["run-1", "tool-1", "a5"]


async def test_delete_removes_the_message_from_the_thread_and_releases_the_lock():
    svc, msgs, conv, ctl, jobs = _service([_msg(10), _msg(11, role="assistant", meta={"lc_ids": ["run-x"]})],
                                          ["m10", "run-x"])
    assert await svc.delete(owner_id=1, message_id=11)
    assert conv.ids == ["m10"] and 11 in msgs.deleted and jobs.items == [] and len(ctl.released) == 1


async def test_deleting_a_summarized_message_rebuilds_the_summary():
    svc, msgs, conv, ctl, jobs = _service([_msg(1), _msg(20)], ["m20"])   # m1 已被压缩进摘要
    assert await svc.delete(owner_id=1, message_id=1)
    assert jobs.items == [(RESUMMARIZE_JOB, {"owner_id": 1, "session_id": 5})]


async def test_edit_replaces_text_in_thread_or_falls_back_to_resummarize():
    svc, msgs, conv, ctl, jobs = _service([_msg(1), _msg(2)], ["m2"])
    await svc.edit(owner_id=1, message_id=2, content="新内容")
    assert conv.texts == {"m2": "新内容"} and jobs.items == []
    await svc.edit(owner_id=1, message_id=1, content="改旧的")
    assert jobs.items and jobs.items[0][0] == RESUMMARIZE_JOB


async def test_voice_transcripts_are_not_editable():
    """语音转写是识别结果，不是用户打的字：改它会把「用户说过什么」记错，
    而它已经进了记忆抽取和对话线程。识别错了就重新说，不提供编辑。"""
    msgs, conv, ctl, jobs = Messages([_msg(50, kind="voice")]), Conversation(["m50"]), Control(), Jobs()
    svc = HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs)

    with pytest.raises(NotEditable):
        await svc.edit(owner_id=1, message_id=50, content="改一下")
    assert msgs.rows[50].content == "c50"      # 一个字都没改
    assert conv.texts == {}                    # 线程也没动


async def test_one_shot_voice_reply_is_not_editable_either():
    """assistant 侧的语音回合（proactive 之类）本来就不是 user 消息，同样编辑不了。"""
    msgs, conv, ctl, jobs = Messages([_msg(51, role="assistant", kind="voice")]), Conversation([]), Control(), Jobs()
    svc = HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs)
    assert await svc.edit(owner_id=1, message_id=51, content="x") is None


async def test_busy_session_refuses_history_changes():
    svc, msgs, *_ = _service([_msg(1)], ["m1"], free=False)
    with pytest.raises(HistoryBusy):
        await svc.delete(owner_id=1, message_id=1)
    assert msgs.deleted == set()   # 没拿到锁就什么都不改


async def test_regenerate_forgets_later_replies_only():
    rows = [_msg(1), _msg(2, role="assistant", meta={"lc_ids": ["r2"]}), _msg(3),
            _msg(4, role="assistant", meta={"lc_ids": ["r4"]})]
    svc, msgs, conv, *_ = _service(rows, ["m1", "r2", "m3", "r4"])
    assert await svc.forget_replies_after(owner_id=1, session_id=5, user_message_id=3) == 1
    assert conv.ids == ["m1", "r2", "m3"]


async def test_interrupted_reply_is_noted_in_the_thread():
    svc, msgs, conv, *_ = _service([], [])
    await svc.note_interrupted(session_id=5, assistant_message_id=9, text="我想说的是")
    assert conv.appended == [("a9", "我想说的是（回复被中断）")]


class Timeline:
    def __init__(self):
        self.stale = []

    async def mark_stale_for_source(self, *, owner_id, message_id):
        self.stale.append((owner_id, message_id))
        return 1


async def test_deleting_a_user_message_stales_its_events():
    """时间线事件跟着用户消息走：消息删了，由它得来的事件作废（chat-agent-timeline-design.md §5）。"""
    msgs, conv, ctl, jobs = Messages([_msg(30), _msg(31, role="assistant")]), Conversation(["m30"]), Control(), Jobs()
    timeline = Timeline()
    svc = HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs, timeline=timeline)

    assert await svc.delete(owner_id=1, message_id=30)
    assert timeline.stale == [("1", "30")]


async def test_editing_a_user_message_stales_its_events():
    msgs, conv, ctl, jobs = Messages([_msg(40)]), Conversation(["m40"]), Control(), Jobs()
    timeline = Timeline()
    svc = HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs, timeline=timeline)

    assert await svc.edit(owner_id=1, message_id=40, content="面试改到周四") is not None
    assert timeline.stale == [("1", "40")]


async def test_a_failing_timeline_does_not_block_deletion():
    class Broken:
        async def mark_stale_for_source(self, **kw):
            raise RuntimeError("db down")

    msgs, conv, ctl, jobs = Messages([_msg(50)]), Conversation(["m50"]), Control(), Jobs()
    svc = HistoryService(messages=msgs, control=ctl, conversation=conv, jobs=jobs, timeline=Broken())
    assert await svc.delete(owner_id=1, message_id=50)


# ---- 候选回复（左右滑动切换）----

def _alt_service(rows, ids):
    return _service(rows, ids)


def _swipe_rows():
    """用户 1 → 候选回复 2（未选中）与 3（选中）。"""
    return [_msg(1), _msg(2, role="assistant", meta={"lc_ids": ["run-a"]}, alt_group=2, alt_selected=False),
            _msg(3, role="assistant", meta={"lc_ids": ["run-b"]}, alt_group=2, alt_selected=True)]


async def test_selecting_an_alternative_swaps_the_reply_in_the_thread():
    svc, msgs, conv, ctl, jobs = _service(_swipe_rows(), ["m1", "run-b"])
    chosen = await svc.select_alternative(owner_id=1, message_id=2)
    assert chosen.id == 2
    assert [m.id for m in msgs.rows.values() if m.alt_selected] == [1, 2]
    assert conv.ids == ["m1"] and conv.appended == [("a2", "c2")]   # 旧回复移除、新候选的文本进线程
    assert jobs.items == [] and len(ctl.released) == 1


async def test_selecting_the_current_alternative_is_a_noop():
    svc, msgs, conv, ctl, jobs = _service(_swipe_rows(), ["m1", "run-b"])
    assert (await svc.select_alternative(owner_id=1, message_id=3)).id == 3
    assert conv.ids == ["m1", "run-b"] and conv.appended == []


async def test_only_the_latest_turn_can_swap_alternatives():
    from companion.app.chat.history import NotLatest

    rows = _swipe_rows() + [_msg(4)]   # 之后又来了一条用户消息
    svc, msgs, conv, ctl, jobs = _service(rows, ["m1", "run-b", "m4"])
    with pytest.raises(NotLatest):
        await svc.select_alternative(owner_id=1, message_id=2)
    assert conv.appended == [] and len(ctl.released) == 1       # 锁照常释放


async def test_selecting_a_summarized_reply_rebuilds_the_summary():
    svc, msgs, conv, ctl, jobs = _service(_swipe_rows(), ["m1"])   # 旧回复已被压缩，线程里没有
    await svc.select_alternative(owner_id=1, message_id=2)
    assert [kind for kind, _ in jobs.items] == [RESUMMARIZE_JOB]


async def test_selecting_while_a_turn_runs_is_busy():
    svc, *_ = _service(_swipe_rows(), ["m1", "run-b"], free=False)
    with pytest.raises(HistoryBusy):
        await svc.select_alternative(owner_id=1, message_id=2)


async def test_non_candidates_cannot_be_selected():
    svc, *_ = _service(_swipe_rows() + [_msg(9, role="assistant")], ["m1"])
    assert await svc.select_alternative(owner_id=1, message_id=9) is None   # 不在任何候选组里
    assert await svc.select_alternative(owner_id=1, message_id=1) is None   # 用户消息


async def test_deleting_the_selected_latest_reply_promotes_the_newest_sibling():
    svc, msgs, conv, ctl, jobs = _service(_swipe_rows(), ["m1", "run-b"])
    assert await svc.delete(owner_id=1, message_id=3)
    assert [m.id for m in msgs.rows.values() if m.alt_selected and m.id not in msgs.deleted] == [1, 2]
    assert conv.ids == ["m1"] and conv.appended == [("a2", "c2")]


async def test_deleting_an_unselected_alternative_leaves_the_thread_alone():
    svc, msgs, conv, ctl, jobs = _service(_swipe_rows(), ["m1", "run-b"])
    assert await svc.delete(owner_id=1, message_id=2)
    assert conv.ids == ["m1", "run-b"] and conv.appended == []


async def test_deleting_a_selected_reply_in_an_older_turn_removes_the_whole_group():
    rows = _swipe_rows() + [_msg(4), _msg(5, role="assistant")]
    svc, msgs, conv, ctl, jobs = _service(rows, ["m1", "run-b", "m4", "a5"])
    assert await svc.delete(owner_id=1, message_id=3)
    assert {2, 3} <= msgs.deleted and conv.appended == []
