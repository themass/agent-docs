"""「喜欢/不喜欢」落库：ca_chat_message.feedback（2026-11-26）。

Android chatkit 的 FeedbackActions 以前只有内存态，刷新即丢；列是 NULL / 'like' / 'dislike'。
用 sqlite_engine 夹具（任何机器都真跑），断言读写往返、切换覆盖、取消，以及
「只有本人名下、未删除的助手消息能带反馈」这条判据。
"""

from companion.db.sql import SqlMessageStore, SqlSessionStore


async def _seed(sqlite_engine, *, owner: int = 7):
    sessions = SqlSessionStore(sqlite_engine)
    messages = SqlMessageStore(sqlite_engine)
    s = await sessions.create(owner_id=owner, role_id="linche", name="t", locale="zh-CN")
    reply = await messages.append(owner_id=owner, session_id=s.id, role="assistant", content="答",
                                  kind="chat", client_message_id=None, turn_id=None, meta={})
    question = await messages.append(owner_id=owner, session_id=s.id, role="user", content="问",
                                     kind="chat", client_message_id=None, turn_id=None, meta={})
    return s, messages, reply, question


async def test_new_message_has_no_feedback(sqlite_engine):
    _s, messages, reply, _q = await _seed(sqlite_engine)
    assert (await messages.get(owner_id=7, message_id=reply.id)).feedback is None


async def test_like_then_dislike_overwrites_then_null_cancels(sqlite_engine):
    """幂等 + 切换即覆盖 + null=取消：一列就够，不需要历史表。"""
    _s, messages, reply, _q = await _seed(sqlite_engine)
    assert await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="like")
    assert (await messages.get(owner_id=7, message_id=reply.id)).feedback == "like"
    # 重复设同一个值仍成功（客户端重试不该报错）
    assert await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="like")
    assert await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="dislike")
    assert (await messages.get(owner_id=7, message_id=reply.id)).feedback == "dislike"
    assert await messages.set_feedback(owner_id=7, message_id=reply.id, feedback=None)
    assert (await messages.get(owner_id=7, message_id=reply.id)).feedback is None


async def test_feedback_survives_a_new_store_instance(sqlite_engine):
    """换一个新的 store 实例（≈进程重启）读到的仍是它——这就是「刷新不再丢」。"""
    _s, messages, reply, _q = await _seed(sqlite_engine)
    await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="like")
    assert SqlMessageStore(sqlite_engine) is not messages
    assert (await SqlMessageStore(sqlite_engine).get(owner_id=7, message_id=reply.id)).feedback == "like"


async def test_history_queries_carry_feedback_back(sqlite_engine):
    """历史接口读的是 list_before：列必须跟着 MessageRecord 回来，端上重绘才有点亮状态。"""
    _s, messages, reply, _q = await _seed(sqlite_engine)
    await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="dislike")
    rows = await messages.list_before(owner_id=7, session_id=_s.id, before_id=None, limit=10)
    by_id = {m.id: m for m in rows}
    assert by_id[reply.id].feedback == "dislike"
    assert by_id[_q.id].feedback is None


async def test_user_messages_and_other_owners_are_refused(sqlite_engine):
    s, messages, reply, question = await _seed(sqlite_engine)
    # 用户自己的消息：反馈是对她的回答的评价
    assert not await messages.set_feedback(owner_id=7, message_id=question.id, feedback="like")
    # 别人的消息：owner_id 隔离（D §5.3）
    assert not await messages.set_feedback(owner_id=8, message_id=reply.id, feedback="like")
    assert (await messages.get(owner_id=7, message_id=reply.id)).feedback is None
    # 已删除的消息不再能被标
    assert await messages.soft_delete(owner_id=7, message_id=reply.id)
    assert not await messages.set_feedback(owner_id=7, message_id=reply.id, feedback="like")
