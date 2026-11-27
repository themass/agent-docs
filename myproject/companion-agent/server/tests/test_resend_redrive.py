"""重发命中幂等时的行为（submit._redrive_duplicate）。

线上事故的样子（2026-11-28，session 39）：原回合 16:47:45 起步、16:47:51 被重启打断，
17:04:45 用户重发 → 被判成 `duplicate`，HTTP 仍是 202。既不起新回合、也不报错，
用户那边是「发了没反应」，客户端随后打了约 40 次 /cancel。

这些用例钉的是：**只有「回合已死且从没回答过」这一种情形会被重驱动**，
其余（活着 / 回答过 / 还在排队）都不许另起回合——那会让同一个人被回答两遍。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from companion.db.port import MessageRecord, QueueItem
from companion.service.chat.submit import SubmitService

_TEXT = "附近的医院"


def _msg(*, message_id: int = 101, turn_id: str | None = "T-OLD",
         content: str = _TEXT, client_id: str | None = "c-1") -> MessageRecord:
    return MessageRecord(id=message_id, session_id=7, owner_id=1, role="user", content=content,
                         kind="chat", client_message_id=client_id, turn_id=turn_id,
                         interrupted=False, created_at=datetime.now(UTC))


@dataclass
class FakeMessages:
    existing: MessageRecord | None
    turn_rows: list[MessageRecord] = field(default_factory=list)

    async def find_by_client_id(self, *, owner_id: int, session_id: int,
                                client_message_id: str) -> MessageRecord | None:
        return self.existing

    async def list_by_turn(self, *, owner_id: int, session_id: int,
                           turn_id: str) -> list[MessageRecord]:
        return list(self.turn_rows)

    async def append(self, **kw: Any) -> MessageRecord:      # 不该被走到
        raise AssertionError("重发路径不该新建消息行")


@dataclass
class FakeQueue:
    items: list[QueueItem] = field(default_factory=list)
    enqueued: list[dict] = field(default_factory=list)

    async def list_status(self, *, owner_id: int, session_id: int, status: str) -> list[QueueItem]:
        return [i for i in self.items if i.status == status]

    async def enqueue(self, **kw: Any) -> QueueItem:
        self.enqueued.append(kw)
        return QueueItem(9, 7, 1, kw["message_id"], kw.get("client_message_id"), kw["text"],
                         "queued", 0, datetime.now(UTC))


@dataclass
class FakeControl:
    active: dict[str, str] | None = None
    lock_granted: bool = True
    published: list[tuple[str, dict]] = field(default_factory=list)

    async def active_turn(self, *, session_id: int) -> dict[str, str] | None:
        return self.active

    async def acquire_lock(self, *, session_id: int, owner: str) -> bool:
        return self.lock_granted

    async def next_fence(self, *, session_id: int) -> int:
        return 1

    async def init_turn(self, *, session_id: int, turn_id: str,
                        message_ids: list[int] | None = None) -> None:
        return None

    async def publish(self, *, session_id: int, event: str, data: dict) -> str:
        self.published.append((event, data))
        return "1-1"

    async def publish_many(self, *, session_id: int,
                           events: list[tuple[str, dict]]) -> None:
        self.published.extend(events)


def _service(*, messages: FakeMessages, queue: FakeQueue, control: FakeControl,
             started: list[dict]) -> SubmitService:
    async def start_turn(**kw: Any) -> None:
        started.append(kw)

    return SubmitService(messages=messages, queue=queue, control=control, start_turn=start_turn)


async def _resend(service: SubmitService) -> Any:
    return await service.submit(owner_id=1, session_id=7, character_id="r1", text=_TEXT,
                                client_message_id="c-1")


async def test_live_turn_resend_stays_a_duplicate():
    """回合还活着：真重复，不许抢它的工作。"""
    started: list[dict] = []
    service = _service(messages=FakeMessages(_msg()), queue=FakeQueue(),
                       control=FakeControl(active={"turn_id": "T-OLD"}), started=started)
    result = await _resend(service)
    assert result.status == "duplicate"
    assert started == []


async def test_answered_turn_resend_stays_a_duplicate():
    """回答过了：重驱动会让用户看到两遍同样的话。"""
    started: list[dict] = []
    answer = MessageRecord(id=202, session_id=7, owner_id=1, role="assistant", content="医院在三公里外",
                           kind="chat", client_message_id=None, turn_id="T-OLD", interrupted=False,
                           created_at=datetime.now(UTC))
    service = _service(messages=FakeMessages(_msg(), turn_rows=[answer]), queue=FakeQueue(),
                       control=FakeControl(active=None), started=started)
    result = await _resend(service)
    assert result.status == "duplicate"
    assert started == []


async def test_queued_message_resend_stays_a_duplicate():
    """turn_id 为空不等于没在处理——排队中的消息就是这个状态。

    少了这一手，「排队时重发」会另起一个回合，同一个人被回答两遍。
    """
    started: list[dict] = []
    queued = QueueItem(5, 7, 1, 101, "c-1", _TEXT, "queued", 0, datetime.now(UTC))
    service = _service(messages=FakeMessages(_msg(turn_id=None)), queue=FakeQueue(items=[queued]),
                       control=FakeControl(active=None), started=started)
    result = await _resend(service)
    assert result.status == "duplicate"
    assert started == []


async def test_dead_unanswered_turn_is_redriven():
    """核心：线上那条就是这种。回 accepted + STARTED，端上不用改。"""
    started: list[dict] = []
    service = _service(messages=FakeMessages(_msg()), queue=FakeQueue(),
                       control=FakeControl(active=None), started=started)
    result = await _resend(service)
    assert result.status == "accepted"
    assert result.turn_id and result.turn_id != "T-OLD"
    assert len(started) == 1
    assert started[0]["message_ids"] == [101]


async def test_dead_turn_but_session_busy_falls_back_to_queue():
    """会话被别的回合占着：转成排队，不能并发驱动，也不能把消息丢回去。"""
    started: list[dict] = []
    queue = FakeQueue()
    control = FakeControl(active=None, lock_granted=False)
    service = _service(messages=FakeMessages(_msg()), queue=queue, control=control, started=started)
    result = await _resend(service)
    assert result.status == "accepted"
    assert result.disposition.value == "queued"
    assert started == []
    assert [e["message_id"] for e in queue.enqueued] == [101]
    assert [e[0] for e in control.published] == ["input.queued"]
