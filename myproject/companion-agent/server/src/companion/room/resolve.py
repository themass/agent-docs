"""一个用户和一个角色该用哪段会话：语音房间、主动开口、文字入口都要问同一个问题。

一个用户和一个角色只有一段对话历史，语音和文字都写进它。所以建语音房间时：

- 客户端带了 ``chat_session_id``：必须属于这个用户，并且角色一致，否则拒绝。
  ``SubmitService`` 本身不校验归属，不在这里挡住，用户就能往别人的会话里写。
- 没带：取这个用户和该角色最近的会话；一次都没聊过才新建。
  不能每次开语音都新建，否则每通电话一段历史，“回到上一次的对话”就没了。
"""

from __future__ import annotations

from companion.store.port import SessionStore

DEFAULT_NAME = "新对话"
DEFAULT_LOCALE = "zh-CN"


class ChatSessionError(Exception):
    """会话号不属于这个用户，或与角色对不上。对外都按“不存在”处理，不泄露别人的会话是否存在。"""


async def resolve_chat_session(sessions: SessionStore, *, user_id: str, character_id: str,
                               chat_session_id: int | None) -> int:
    if not user_id.isdigit():
        raise ChatSessionError("user id must be numeric")
    owner_id = int(user_id)

    if chat_session_id is not None:
        record = await sessions.get(owner_id=owner_id, session_id=chat_session_id)
        if record is None or record.role_id != character_id:
            raise ChatSessionError("chat session not found")
        return record.id

    latest = await sessions.latest_for_role(owner_id=owner_id, role_id=character_id)
    if latest is not None:
        return latest.id
    created = await sessions.create(owner_id=owner_id, role_id=character_id,
                                    name=DEFAULT_NAME, locale=DEFAULT_LOCALE)
    return created.id
