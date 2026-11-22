"""``control.input`` 的多 kind 分发与附件暂存槽（图片消息 P1 服务端侧）。

端侧顺序是「先发 attachments 事件，再发文字」（Task 4 客户端如此），但两条消息走的是
不同通道（数据通道 vs lk.chat），服务端**不能假设**到达顺序。这里锁的是：

1. 分发：``kind=touch`` 走原触摸路径，``kind=attachments`` 进槽，未知 kind 两边都不碰。
2. 合并：下一回合 ``submit`` 收到 ``attachments=[{"upload_id":..,"kind":"image"}]``，槽被清空。
3. 乱序：文字先到 → 本轮按纯文本走，槽保留给下一个回合，并记一条 warn（图不丢）。
4. TTL：过期即空，不抛异常。
5. 幂等：同 ``client_msg_id`` 重复投递不翻倍。
6. 上限与脏数据：put 拒绝 + warn，槽原样不动。

全部是纯内存对象 + 假 session/假 submit，不需要 Redis 与 Postgres。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from companion.agent.protocol import TOPIC_IN, encode, new_envelope
from companion.api.livekit.input_attachments import (
    PENDING_TTL_SEC,
    CompositeInputRelay,
    PendingAttachmentSlot,
)
from companion.api.livekit.protocol_bridge import ProtocolBridge
from companion.service.uploads.policy import MAX_MESSAGE_ATTACHMENTS

CLIENT = "user-1002"
AGENT = "agent-linche"


# ---------------------------------------------------------------- 替身

class _Clock:
    """可控时钟：测试里手动推进，不用 sleep。"""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


class _Session:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_reply(self, *, user_input: str) -> None:
        self.calls.append(user_input)


class _Sink:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def __call__(self, topic: str, payload: bytes) -> None:
        self.sent.append((topic, payload))


def _bridge(sink: _Sink | None = None) -> ProtocolBridge:
    return ProtocolBridge(send=sink or _Sink(), identity=AGENT, local_identity=AGENT,
                          sid="s-test", legacy_timeout=0.05)


def _attachments_args(ids: Any, client_msg_id: str = "att-1") -> dict[str, Any]:
    return {"kind": "attachments", "upload_ids": ids, "client_msg_id": client_msg_id}


# ---------------------------------------------------------------- 1. 分发

def test_attachments_kind_goes_to_the_slot_not_the_session():
    session = _Session()
    slot = PendingAttachmentSlot()
    relay = CompositeInputRelay(session, slot)

    relay(_attachments_args(["01A", "01B"], client_msg_id="att-42"))

    assert session.calls == []          # 附件绝不能被当成一句话
    assert slot.consume() == ["01A", "01B"]
    assert relay.ignored == 0


def test_touch_kind_still_reaches_generate_reply():
    """触摸回归：换成分发器之后，冷却语义与原来必须一模一样。"""
    session = _Session()
    relay = CompositeInputRelay(session, PendingAttachmentSlot(), cooldown_s=60.0)

    relay({"kind": "touch", "region": "head"})
    relay({"kind": "touch", "region": "body"})   # 冷却内

    assert session.calls == ["摸了摸她的头"]
    assert relay.touch.accepted == 1
    assert relay.touch.ignored == 1


def test_unknown_kind_touches_neither_branch():
    session = _Session()
    slot = PendingAttachmentSlot()
    relay = CompositeInputRelay(session, slot)

    relay({"kind": "swipe", "region": "head"})
    relay({"region": "head"})
    relay(None)

    assert session.calls == []
    assert slot.consume() == []
    assert relay.ignored == 3


@pytest.mark.asyncio
async def test_bridge_delivers_an_attachments_event_to_the_slot():
    """端到端接线：``bridge.on_data`` 收到 control.input(kind=attachments) 就进槽。"""
    bridge = _bridge()
    slot = PendingAttachmentSlot()
    bridge.on_input = CompositeInputRelay(_Session(), slot)
    payload = encode(new_envelope("control.input", args=_attachments_args(["01XYZ"], "in-att"),
                                  seq=0, ep="ep-a", ident="in-att"))

    await bridge.on_data(payload, topic=TOPIC_IN, publisher_identity=CLIENT, publisher_kind="STANDARD")

    assert slot.consume() == ["01XYZ"]
    assert bridge.unhandled == {}


# ---------------------------------------------------------------- 2. 合并进 submit

class _FakeControl:
    async def tail_event_id(self, *, session_id: int) -> str:
        return "0-0"

    async def wait_events(self, *, session_id: int, after_id: str, block_ms: int):
        await asyncio.sleep(0.01)
        return []

    async def send_cancel(self, *, turn_id: str) -> None:
        return None


class _FakeSubmit:
    """只记录提交参数；disposition=None 让 brain 走「不支持的 disposition」分支立刻收尾，
    测试关心的只有 submit 收到的 attachments 参数。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def submit(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(status="accepted", disposition=None, message_id=11,
                               turn_id=None, reason=None)


async def _start_turn(brain, text: str = "这是什么") -> None:
    from companion.agent.brain.port import TurnRequest

    turn = await brain.start_turn(TurnRequest(user_id="1002", character_id="linche",
                                              message=text, session_id=7))
    [chunk async for chunk in turn.tokens]     # 走完流，别留下未收尾的协程


async def test_slot_contents_are_merged_into_the_next_turn():
    from companion.service.turns.platform_brain import PlatformBrain

    slot = PendingAttachmentSlot()
    submit = _FakeSubmit()
    brain = PlatformBrain(submit=submit, control=_FakeControl(), pending_attachments=slot)
    slot.put(["01A", "01B"], client_msg_id="att-1")

    await _start_turn(brain)

    assert submit.calls[0]["attachments"] == [{"upload_id": "01A", "kind": "image"},
                                              {"upload_id": "01B", "kind": "image"}]
    assert slot.consume() == []          # 消费即清：不会带到第三个回合


async def test_empty_slot_keeps_the_turn_pure_text():
    """现状回归：没有附件时 submit 收到 attachments=None，行为与改动前完全一致。"""
    from companion.service.turns.platform_brain import PlatformBrain

    submit = _FakeSubmit()
    brain = PlatformBrain(submit=submit, control=_FakeControl(), pending_attachments=PendingAttachmentSlot())

    await _start_turn(brain)

    assert submit.calls[0]["attachments"] is None


async def test_brain_without_a_slot_is_unchanged():
    """后台主动回合等调用方不传槽，参数保持默认。"""
    from companion.service.turns.platform_brain import PlatformBrain

    submit = _FakeSubmit()
    await _start_turn(PlatformBrain(submit=submit, control=_FakeControl()))
    assert submit.calls[0]["attachments"] is None


# ---------------------------------------------------------------- 3. 乱序（Review Focus 1）

async def test_text_before_the_attachments_event_keeps_the_images_for_the_next_turn(caplog):
    """文字先到：本轮按纯文本提交，槽保留给下一回合，并记一条 warn（图不丢）。"""
    from companion.service.turns.platform_brain import PlatformBrain

    slot = PendingAttachmentSlot()
    submit = _FakeSubmit()
    brain = PlatformBrain(submit=submit, control=_FakeControl(), pending_attachments=slot)

    with caplog.at_level("WARNING"):
        await _start_turn(brain)                          # 文字先到，槽还是空
        slot.put(["01A", "01B"], client_msg_id="att-1")   # attachments 事件后到
        await _start_turn(brain)                          # 下一回合带上图

    assert submit.calls[0]["attachments"] is None
    assert submit.calls[1]["attachments"] == [{"upload_id": "01A", "kind": "image"},
                                              {"upload_id": "01B", "kind": "image"}]
    assert any("attach" in r.getMessage().lower() for r in caplog.records)


# ---------------------------------------------------------------- 4. TTL（Review Focus 2）

def test_expired_slot_consumes_empty_without_raising():
    clock = _Clock()
    slot = PendingAttachmentSlot(clock=clock)
    slot.put(["01A"], client_msg_id="att-1")

    clock.advance(PENDING_TTL_SEC - 1)
    assert slot.consume() == ["01A"]

    slot.put(["01B"], client_msg_id="att-2")
    clock.advance(PENDING_TTL_SEC + 1)
    assert slot.consume() == []


def test_ttl_is_sixty_seconds():
    assert PENDING_TTL_SEC == 60


# ---------------------------------------------------------------- 5. 幂等（Review Focus 3）

def test_the_same_client_msg_id_does_not_double_the_ids():
    slot = PendingAttachmentSlot()
    slot.put(["01A", "01B"], client_msg_id="att-1")
    slot.put(["01A", "01B"], client_msg_id="att-1")   # 重发（MUST 语义下可能发生）

    assert slot.consume() == ["01A", "01B"]


def test_a_retransmit_late_from_behind_the_turn_does_not_reattach_the_images():
    """重传比消费更晚到（数据通道重传没有时限）：这批图已经并入过一条消息了。

    槽此时是空的，只看槽分不出「重发」和「用户新发了一条带图消息」——不记消费过
    哪一批的话，这批图会贴到用户的下一条消息上，而那条消息压根没带图。
    """
    slot = PendingAttachmentSlot()
    slot.put(["01A", "01B"], client_msg_id="att-1")
    assert slot.consume() == ["01A", "01B"]

    assert slot.put(["01A", "01B"], client_msg_id="att-1") is True   # 迟到的重传
    assert slot.consume() == []


def test_a_real_new_batch_still_goes_through_after_a_late_retransmit_was_dropped():
    """幂等只挡同一条消息，不能把用户下一条消息的图一起挡掉。"""
    slot = PendingAttachmentSlot()
    slot.put(["01A"], client_msg_id="att-1")
    assert slot.consume() == ["01A"]
    slot.put(["01A"], client_msg_id="att-1")          # 迟到的重传 → 丢弃

    assert slot.put(["01B"], client_msg_id="att-2") is True
    assert slot.consume() == ["01B"]


def test_a_different_client_msg_id_overrides_the_slot():
    """覆盖语义：一批新的附件替换掉还没被消费的那一批。"""
    slot = PendingAttachmentSlot()
    slot.put(["01OLD"], client_msg_id="att-1")
    slot.put(["01NEW"], client_msg_id="att-2")

    assert slot.consume() == ["01NEW"]


# ---------------------------------------------------------------- 6. 上限与脏数据

@pytest.mark.parametrize("ids", [
    [],                                        # 空批
    ["01A"] * (MAX_MESSAGE_ATTACHMENTS + 1),   # 超上限
    "01A",                                     # 不是 list
    None,
    ["01A", 42],                               # 混入非 str
    ["01A", ""],                               # 空串 id
])
def test_bad_or_oversized_payloads_are_refused_without_touching_the_slot(ids: Any, caplog):
    slot = PendingAttachmentSlot()
    slot.put(["01KEEP"], client_msg_id="att-1")

    with caplog.at_level("WARNING"):
        assert slot.put(ids, client_msg_id="att-2") is False

    assert slot.consume() == ["01KEEP"]    # 坏投递不许把已有附件冲掉
    assert caplog.records


def test_max_message_attachments_is_nine():
    """这个常数是 HTTP 上传与消息附件两处校验的本家（Task 6 的 SendBody 也 import 它）。"""
    assert MAX_MESSAGE_ATTACHMENTS == 9


def test_a_batch_at_the_limit_is_accepted():
    slot = PendingAttachmentSlot()
    ids = [f"01{i:02d}" for i in range(MAX_MESSAGE_ATTACHMENTS)]
    assert slot.put(ids, client_msg_id="att-1") is True
    assert slot.consume() == ids


# ---------------------------------------------------------------- 7. 装配：同一个槽喂两路

async def test_the_composition_root_hands_the_same_slot_to_the_brain():
    """``VoiceWiring`` 必须把入口构造的那一个槽交给 ``PlatformBrain``。

    两路不是同一个实例的话，事件写进 A、回合读 B，功能整体失效且没有任何报错。
    """
    from companion.bootstrap.voice_wiring import voice_wiring

    slot = PendingAttachmentSlot()
    submit = _FakeSubmit()
    platform = SimpleNamespace(qa=None, qa_enabled=False,
                               chat=SimpleNamespace(submit=submit, control=_FakeControl()))
    parts = voice_wiring()(platform, "card_voice", slot)
    slot.put(["01A"], client_msg_id="att-1")

    await _start_turn(parts.brain)

    assert parts.brain._pending is slot
    assert submit.calls[0]["attachments"] == [{"upload_id": "01A", "kind": "image"}]


def test_the_wiring_still_works_without_a_slot():
    from companion.bootstrap.voice_wiring import voice_wiring

    platform = SimpleNamespace(qa=None, qa_enabled=False,
                               chat=SimpleNamespace(submit=object(), control=object()))
    assert voice_wiring()(platform).brain is not None
