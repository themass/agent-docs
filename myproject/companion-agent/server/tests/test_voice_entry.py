"""语音房间入口：身份解析、会话必填、被拒绝输入的回复。

这一段原来没有任何测试，而它正是“语音和文字是两条路”的出处，所以这里守住三条：
房间必须带 chat_session_id（不再退回独立语音会话）、请求带上会话号、被拒绝的输入有一句回复。
"""

import json
from types import SimpleNamespace

import pytest

from companion.agent.brain.port import TurnRefused
from companion.api.livekit.agent import (
    REFUSED_LINE,
    UNAVAILABLE_LINE,
    build_agent_class,
    build_request,
    last_user_message,
)
from companion.api.livekit.entrypoint import RoomIdentity, make_entrypoint


def _meta(**kw) -> str:
    return json.dumps({"user_id": "1002", "character_id": "linche", **kw})


def test_identity_carries_the_chat_session_id():
    ident = RoomIdentity.from_room_metadata(_meta(chat_session_id=42))
    assert (ident.user_id, ident.character_id, ident.chat_session_id) == ("1002", "linche", 42)


@pytest.mark.parametrize("bad", ["abc", 0, -3])
def test_a_broken_session_id_is_refused(bad):
    with pytest.raises(ValueError):
        RoomIdentity.from_room_metadata(_meta(chat_session_id=bad))


def test_the_request_uses_the_chat_session_so_history_is_shared():
    req = build_request(user_id="1002", character_id="linche", message="你好", chat_session_id=42)
    assert req.session_id == 42
    assert req.user_id == "1002"


def test_last_user_message_picks_the_latest_user_turn():
    ctx = SimpleNamespace(items=[
        SimpleNamespace(role="user", text_content="第一句"),
        SimpleNamespace(role="assistant", text_content="回答"),
        SimpleNamespace(role="user", text_content=" 第二句 "),
    ])
    assert last_user_message(ctx) == "第二句"


class _Pipeline:
    last_turn = None     # 真管线在回合开始后才有；这里没有回合，记录端据此跳过

    def __init__(self, outputs=(), error=None):
        self.outputs, self.error, self.requests = outputs, error, []

    async def run(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        for text in self.outputs:
            yield SimpleNamespace(text=text, events=[])


async def _say(pipeline) -> list[str]:
    agent = build_agent_class()(pipeline=pipeline, user_id="1002", character_id="linche", chat_session_id=42)
    ctx = SimpleNamespace(items=[SimpleNamespace(role="user", text_content="今天好累")])
    return [s async for s in agent.llm_node(ctx, [], None)]


async def test_sentences_are_forwarded_and_the_session_is_passed():
    pipeline = _Pipeline(outputs=["先歇一会儿。", "我在。"])
    assert await _say(pipeline) == ["先歇一会儿。", "我在。"]
    assert pipeline.requests[0].session_id == 42


async def test_a_refused_input_gets_a_spoken_reply_not_silence():
    assert await _say(_Pipeline(error=TurnRefused("blocked"))) == [REFUSED_LINE]


async def test_a_turn_that_cannot_start_gets_a_spoken_reply():
    assert await _say(_Pipeline(error=ValueError("no session"))) == [UNAVAILABLE_LINE]


class _Room:
    def __init__(self, metadata):
        self.metadata = metadata
        self.disconnected = False

    async def disconnect(self):
        self.disconnected = True


class _Ctx:
    """假的 JobContext。

    ``connected`` 记的是入口有没有先连房间——这条很关键：metadata 在连接之前读到的是
    空值，而原来的入口正是在连接前读的，于是每个房间都被拒。真实 SDK 的文档写着
    "Certain properties of Room would not be available before calling JobContext.connect()"。
    """

    def __init__(self, room):
        self.room = room
        self.connected = False
        self.shutdown_callbacks = []

    async def connect(self):
        self.connected = True

    def add_shutdown_callback(self, cb):
        self.shutdown_callbacks.append(cb)


async def _enter(metadata):
    built = []

    async def factory():
        built.append(1)
        raise AssertionError("platform must not be built for a refused room")

    room = _Room(metadata)
    ctx = _Ctx(room)
    await make_entrypoint(factory)(ctx)
    return room, built, ctx


async def test_a_room_without_a_chat_session_is_refused_before_anything_is_built():
    room, built, ctx = await _enter(_meta())
    assert ctx.connected          # 必须先连上，metadata 才读得到
    assert room.disconnected and built == []


async def test_a_room_without_metadata_is_refused():
    room, built, ctx = await _enter(None)
    assert ctx.connected
    assert room.disconnected and built == []
