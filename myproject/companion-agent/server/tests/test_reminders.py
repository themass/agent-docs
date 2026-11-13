"""定时提醒的领域规则与调度器（存储用内存假实现；多副本互斥在 Postgres 集成测试里验证）。"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from companion.service.proactive.reminders import ReminderDispatcher
from companion.service.proactive.model import ReminderInvalid, normalize_content, normalize_due, proactive_instruction
from companion.service.proactive.port import ReminderRecord

NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)
CST = timezone(timedelta(hours=8))


def test_due_time_is_converted_to_naive_utc():
    due = normalize_due(datetime(2026, 11, 12, 15, 0, tzinfo=CST), timezone="Asia/Shanghai", now=NOW)
    assert due.utc == datetime(2026, 11, 12, 7, 0) and due.timezone == "Asia/Shanghai"


@pytest.mark.parametrize("at,tz", [
    (datetime(2026, 11, 11, 8, 0, 30, tzinfo=UTC), "UTC"),          # 不到一分钟
    (datetime(2028, 1, 1, tzinfo=UTC), "UTC"),                      # 超过一年
    (datetime(2026, 11, 12, 8, 0), "UTC"),                          # 没有时区
    (datetime(2026, 11, 12, 8, 0, tzinfo=UTC), "Mars/Olympus"),     # 未知时区
])
def test_invalid_due_times_are_rejected(at, tz):
    with pytest.raises(ReminderInvalid):
        normalize_due(at, timezone=tz, now=NOW)


def test_content_is_collapsed_and_bounded():
    assert normalize_content("  叫我\n开会 ") == "叫我 开会"
    with pytest.raises(ReminderInvalid):
        normalize_content("   ")
    with pytest.raises(ReminderInvalid):
        normalize_content("长" * 201)


def test_instruction_uses_local_time_and_never_says_system():
    text = proactive_instruction(content="开会", due_utc=datetime(2026, 11, 12, 7, 0), timezone="Asia/Shanghai")
    assert "2026-11-12 15:00" in text and "开会" in text


class Store:
    def __init__(self, items):
        self.items = {i.id: i for i in items}
        self.sent, self.released = [], []

    async def claim_due(self, *, owner, now, lease_until, limit):
        return [i for i in self.items.values() if i.due_at <= now][:limit]

    async def mark_sent(self, *, reminder_id, owner, turn_id):
        self.sent.append((reminder_id, turn_id))
        return True

    async def release(self, *, reminder_id, owner, error, retry_at, max_attempts):
        self.released.append((reminder_id, error, retry_at))
        return True


def _rem(rid, owner_id=7):
    return ReminderRecord(id=rid, owner_id=owner_id, session_id=3, role_id="linche", due_at=datetime(2026, 11, 11, 7),
                          timezone="UTC", content="喝水", status="claimed", attempts=1, created_at=datetime(2026, 11, 1))


async def test_dispatcher_submits_a_proactive_turn_marks_sent_and_pushes():
    submitted, pushed = [], []

    async def submit(owner_id, session_id, role_id, text):
        submitted.append((owner_id, session_id, role_id, text))
        return "turn-1"

    class Push:
        async def send(self, message):
            pushed.append(message)
            return True

    store = Store([_rem(1)])
    n = await ReminderDispatcher(store=store, submit=submit, owner="w1", push=Push()).run_once(NOW)
    assert n == 1 and store.sent == [(1, "turn-1")]
    assert submitted[0][:3] == (7, 3, "linche") and "喝水" in submitted[0][3]
    assert pushed[0].owner_id == 7 and pushed[0].data["session_id"] == "3"


async def test_dispatch_failure_releases_for_retry():
    async def submit(*args):
        raise ConnectionError("redis down")

    store = Store([_rem(2)])
    await ReminderDispatcher(store=store, submit=submit, owner="w1").run_once(NOW)
    assert store.sent == [] and store.released[0][:2] == (2, "ConnectionError")
