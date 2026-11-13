"""语音房间绑定哪段聊天历史：归属校验、角色一致、复用而不是每次新建。"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from companion.service.room.resolve import ChatSessionError, resolve_chat_session


class Sessions:
    def __init__(self):
        self.rows = {}

    async def get(self, *, owner_id, session_id):
        r = self.rows.get(session_id)
        return r if r and r.owner_id == owner_id else None

    async def latest_for_role(self, *, owner_id, role_id):
        mine = [r for r in self.rows.values() if r.owner_id == owner_id and r.role_id == role_id]
        return mine[-1] if mine else None

    async def create(self, *, owner_id, role_id, name, locale):
        sid = len(self.rows) + 1
        self.rows[sid] = SimpleNamespace(id=sid, owner_id=owner_id, role_id=role_id, name=name, locale=locale,
                                         updated_at=datetime.now(UTC))
        return self.rows[sid]


async def _resolve(sessions, *, user="1002", role="linche", sid=None):
    return await resolve_chat_session(sessions, user_id=user, character_id=role, chat_session_id=sid)


async def test_the_first_call_creates_a_session_and_later_calls_reuse_it():
    s = Sessions()
    first = await _resolve(s)
    assert await _resolve(s) == first
    assert len(s.rows) == 1


async def test_each_role_has_its_own_session():
    s = Sessions()
    a, b = await _resolve(s, role="linche"), await _resolve(s, role="sudai")
    assert a != b


async def test_each_user_has_its_own_session():
    s = Sessions()
    assert await _resolve(s, user="1002") != await _resolve(s, user="1003")


async def test_an_explicit_session_of_the_same_user_and_role_is_used():
    s = Sessions()
    mine = await _resolve(s)
    again = await _resolve(s, sid=mine)
    assert again == mine


async def test_someone_elses_session_is_refused():
    s = Sessions()
    theirs = await _resolve(s, user="1003")
    with pytest.raises(ChatSessionError):
        await _resolve(s, user="1002", sid=theirs)


async def test_a_session_of_another_role_is_refused():
    # 拿着林澈的会话号去开苏黛的语音，会把苏黛的话写进林澈的历史
    s = Sessions()
    linche = await _resolve(s, role="linche")
    with pytest.raises(ChatSessionError):
        await _resolve(s, role="sudai", sid=linche)


async def test_an_unknown_session_is_refused():
    with pytest.raises(ChatSessionError):
        await _resolve(Sessions(), sid=999)


async def test_a_non_numeric_user_is_refused_without_creating_anything():
    s = Sessions()
    with pytest.raises(ChatSessionError):
        await _resolve(s, user="alice")
    assert s.rows == {}
