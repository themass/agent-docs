"""历史操作：编辑、删除、重新生成时消息表与对话线程保持一致。"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from companion.app.chat.history import HistoryBusy, HistoryService, lc_ids_of
from companion.domain.history.summary import RESUMMARIZE_JOB


def _msg(mid, role="user", meta=None, kind="chat", session_id=5):
    return SimpleNamespace(id=mid, session_id=session_id, owner_id=1, role=role, content=f"c{mid}", kind=kind,
                           meta=meta or {}, created_at=datetime.now(UTC), interrupted=False, turn_id=None,
                           client_message_id=None)


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
        return [m for i, m in sorted(self.rows.items()) if i > after_id and i not in self.deleted][:limit]


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
