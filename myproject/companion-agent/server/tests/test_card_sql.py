"""角色卡的 SQL 存储（ca_role_card / ca_role_card_version）。

与 fake 版跑同一套语义断言（sqlite_engine 夹具）；唯一约束在并发重复创建时兜底。
"""

from __future__ import annotations

import pytest

from companion.service.card.model import merge_chain
from companion.service.card.sql import SqlCardStore
from companion.service.card.store import CardService


@pytest.fixture
def service(sqlite_engine):
    return CardService(SqlCardStore(sqlite_engine))


async def test_create_then_effective(service):
    await service.create(owner_id=7, role_id="linche", base={"name": "临澈", "description": "原"})
    eff = await service.effective(owner_id=7, role_id="linche")
    assert eff.version == 1
    assert eff.fields == {"name": "临澈", "description": "原"}


async def test_append_and_rollback_round_trip(service):
    await service.create(owner_id=7, role_id="linche", base={"description": "一"})
    v2 = await service.append_version(owner_id=7, role_id="linche", changes={"description": "二"})
    assert v2.version == 2
    await service.rollback(owner_id=7, role_id="linche", version=1)
    assert (await service.effective(owner_id=7, role_id="linche")).fields["description"] == "一"
    versions = await service.list_versions(owner_id=7, role_id="linche")
    assert [(v.version, v.changes) for v in versions] == [(1, {}), (2, {"description": "二"})]


async def test_set_active_persists_across_store_instances(sqlite_engine):
    """active_version 落在卡行上：换一个新的 store 实例（≈进程重启）读到的仍是它。"""
    s1 = CardService(SqlCardStore(sqlite_engine))
    await s1.create(owner_id=7, role_id="linche", base={})
    await s1.append_version(owner_id=7, role_id="linche", changes={"personality": "冷淡"})
    await s1.set_active(owner_id=7, role_id="linche", version=1)
    s2 = CardService(SqlCardStore(sqlite_engine))
    assert (await s2.effective(owner_id=7, role_id="linche")).version == 1


async def test_owner_and_role_isolation(service):
    await service.create(owner_id=7, role_id="linche", base={"name": "我的"})
    assert await service.effective(owner_id=8, role_id="linche") is None
    await service.create(owner_id=7, role_id="sudai", base={"name": "苏黛"})
    assert (await service.effective(owner_id=7, role_id="sudai")).fields["name"] == "苏黛"
    assert (await service.effective(owner_id=7, role_id="linche")).fields["name"] == "我的"


async def test_double_create_is_rejected(service):
    from companion.service.card.store import CardNotFound

    await service.create(owner_id=7, role_id="linche", base={})
    with pytest.raises(CardNotFound):
        await service.create(owner_id=7, role_id="linche", base={})
    # 失败的第二次创建没有污染第一张卡
    assert (await service.list_versions(owner_id=7, role_id="linche"))[-1].version == 1


async def test_rollback_to_missing_version_raises(service):
    from companion.service.card.store import CardNotFound

    await service.create(owner_id=7, role_id="linche", base={})
    with pytest.raises(CardNotFound):
        await service.set_active(owner_id=7, role_id="linche", version=42)


async def test_changes_round_trip_unicode_and_types(service):
    await service.create(owner_id=7, role_id="linche", base={})
    changes = {"boundaries": ["不谈钱", "不聊工作"], "voice": {"speed": 0.9, "engine": "volc"}}
    await service.append_version(owner_id=7, role_id="linche", changes=changes)
    stored = (await service.list_versions(owner_id=7, role_id="linche"))[-1].changes
    assert stored == changes
    eff = await service.effective(owner_id=7, role_id="linche")
    assert merge_chain({}, [stored])["voice"]["speed"] == 0.9
