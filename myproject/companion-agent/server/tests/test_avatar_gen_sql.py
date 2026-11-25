"""头像生成账本与头像指针的 SQL 语义（sqlite_engine 夹具，任何机器都真跑）。

钉三件内存替身钉不住的事：
1. 配额窗口按 created_at 滚动（「一天前」的行不再计入）；
2. ``due_sources`` 按源去重 + 只认未清理的行（``expires_at`` 非空且到点）；
3. 指针的 upsert：同一用户重复 set 不炸、只留最后一张。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from companion.service.avatar_gen.sql import SqlAvatarGenAttemptStore, SqlUserAvatarStore

NOW = datetime(2026, 11, 25, 10, 0)


def _row(attempt_id: int = 0, owner: int = 7, source: str = "01SRC0000000000000000000AA"):
    return dict(owner_id=owner, source_upload_id=source, source_key=f"companion/uploads/{owner}/{source}.jpg",
                style="anime", created_at=NOW, expires_at=NOW + timedelta(hours=20))


async def test_quota_window_counts_only_recent_attempts(sqlite_engine):
    store = SqlAvatarGenAttemptStore(sqlite_engine)
    await store.add_attempt(**_row())
    await store.add_attempt(**{**_row(), "created_at": NOW - timedelta(hours=25)})
    assert await store.count_recent(owner_id=7, since=NOW - timedelta(hours=24)) == 1
    assert await store.count_recent(owner_id=8, since=NOW - timedelta(hours=24)) == 0


async def test_attempt_returns_id_and_attaches_result_for_apply(sqlite_engine):
    store = SqlAvatarGenAttemptStore(sqlite_engine)
    attempt_id = await store.add_attempt(**_row())
    assert await store.result_owned(owner_id=7, upload_id="01RES0000000000000000000BB") is False

    await store.attach_result(attempt_id=attempt_id, result_upload_id="01RES0000000000000000000BB")
    assert await store.result_owned(owner_id=7, upload_id="01RES0000000000000000000BB") is True
    # 别人的结果不算自己的（apply 的归属半边）
    assert await store.result_owned(owner_id=8, upload_id="01RES0000000000000000000BB") is False


async def test_due_sources_dedupe_and_boundary(sqlite_engine):
    store = SqlAvatarGenAttemptStore(sqlite_engine)
    # 同一源图两次尝试（重试）：只出一条
    await store.add_attempt(**_row())
    await store.add_attempt(**{**_row(), "created_at": NOW + timedelta(minutes=5)})
    # 没到点的源（expires_at 在未来）不出
    await store.add_attempt(**{**_row(), "owner_id": 9, "source_upload_id": "01LATER0000000000000000000",
                               "expires_at": NOW + timedelta(hours=21)})
    # 已清理的（expires_at 为空）不出
    await store.add_attempt(**{**_row(), "owner_id": 10, "source_upload_id": "01PURGED000000000000000000",
                               "expires_at": None})

    due = await store.due_sources(now=NOW + timedelta(hours=20), limit=50)
    assert [(s.upload_id, s.owner_id) for s in due] == [("01SRC0000000000000000000AA", 7)]
    assert due[0].object_key == "companion/uploads/7/01SRC0000000000000000000AA.jpg"

    # 边界：到点即到期（<=），所以「没到点」的那条在 21h 整会出现——这是对的，
    # 上面 20h 时它不出现才是真正的断言。
    assert [s.upload_id for s in await store.due_sources(now=NOW + timedelta(hours=21), limit=50)] == [
        "01SRC0000000000000000000AA", "01LATER0000000000000000000"]

    await store.mark_source_purged(source_upload_id="01SRC0000000000000000000AA")
    # 已清理的不再重复扫（20h 窗口里 LATER 仍未到期、SRC 已清）
    assert await store.due_sources(now=NOW + timedelta(hours=20), limit=50) == []
    # 行还在：配额窗口与 apply 认领仍看得见它
    assert await store.count_recent(owner_id=7, since=NOW - timedelta(minutes=1)) == 2


async def test_pointer_upsert_keeps_one_row_per_user(sqlite_engine):
    ptr = SqlUserAvatarStore(sqlite_engine)
    assert await ptr.get(owner_id=7) is None
    await ptr.set(owner_id=7, upload_id="01AAA000000000000000000000")
    await ptr.set(owner_id=7, upload_id="01BBB000000000000000000000")
    assert await ptr.get(owner_id=7) == "01BBB000000000000000000000"
    assert await ptr.get(owner_id=8) is None

    await ptr.delete(owner_id=7)
    assert await ptr.get(owner_id=7) is None
