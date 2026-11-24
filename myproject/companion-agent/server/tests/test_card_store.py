"""角色卡存储与版本解析（P6）。fake store 先钉语义，SQL 实现随后照同一套断言跑。

关键语义：`active_version` 是提示词读的那一个版本号；生效字段 = 基准 + 版本号 ≤ active 的
变更集按序叠加。回退 = 把 active 往回挪，历史版本不删。
"""

from __future__ import annotations

import pytest

from companion.service.card.model import CardChangeInvalid
from companion.service.card.store import CardNotFound, InMemoryCardStore, CardService


def _service() -> tuple[CardService, InMemoryCardStore]:
    store = InMemoryCardStore()
    return CardService(store), store


async def test_create_makes_version_one_active():
    service, _ = _service()
    card = await service.create(owner_id=7, role_id="linche", base={"name": "临澈"})
    assert card.active_version == 1
    assert card.version_count == 1
    effective = await service.effective(owner_id=7, role_id="linche")
    assert effective.version == 1
    assert effective.fields == {"name": "临澈"}


async def test_append_advances_active_to_new_version():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={"description": "原"})
    v2 = await service.append_version(owner_id=7, role_id="linche", changes={"description": "新"})
    assert v2.version == 2
    effective = await service.effective(owner_id=7, role_id="linche")
    assert effective.version == 2
    assert effective.fields["description"] == "新"


async def test_rollback_makes_older_active_and_keeps_history():
    service, store = _service()
    await service.create(owner_id=7, role_id="linche", base={"description": "一"})
    await service.append_version(owner_id=7, role_id="linche", changes={"description": "二"})
    await service.rollback(owner_id=7, role_id="linche", version=1)
    effective = await service.effective(owner_id=7, role_id="linche")
    assert effective.version == 1
    assert effective.fields["description"] == "一"
    versions = await service.list_versions(owner_id=7, role_id="linche")
    assert [v.version for v in versions] == [1, 2]  # 历史还在，可观


async def test_append_after_rollback_advances_again():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={})
    await service.append_version(owner_id=7, role_id="linche", changes={"name": "A"})
    await service.append_version(owner_id=7, role_id="linche", changes={"name": "B"})
    await service.rollback(owner_id=7, role_id="linche", version=1)
    v4 = await service.append_version(owner_id=7, role_id="linche", changes={"name": "C"})
    assert v4.version == 4
    assert (await service.effective(owner_id=7, role_id="linche")).fields["name"] == "C"


async def test_active_version_truncates_the_chain():
    """active=1 时，后来写的版本存在但不生效——这是「prompt 吃 active version」的含义。"""
    service, store = _service()
    await service.create(owner_id=7, role_id="linche", base={})
    await service.append_version(owner_id=7, role_id="linche", changes={"personality": "冷淡"})
    await service.set_active(owner_id=7, role_id="linche", version=1)
    assert (await service.effective(owner_id=7, role_id="linche")).fields == {}
    await service.set_active(owner_id=7, role_id="linche", version=2)
    assert (await service.effective(owner_id=7, role_id="linche")).fields == {"personality": "冷淡"}


async def test_append_without_card_creates_version_one():
    """API 没有独立的「建卡」调用：第一次 append 就是 v1（base 为空）。"""
    service, _ = _service()
    v = await service.append_version(owner_id=7, role_id="linche", changes={"name": "小澈"})
    assert v.version == 1
    eff = await service.effective(owner_id=7, role_id="linche")
    assert eff.version == 1 and eff.fields == {"name": "小澈"}
    # 之后照常递增
    v2 = await service.append_version(owner_id=7, role_id="linche", changes={"name": "临澈"})
    assert v2.version == 2


async def test_owner_isolation():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={"name": "我的"})
    # 「不存在」与「不是你的」对调用方不可区分（同记忆接口 delete_one 的口径）：都读成 None / 空
    assert await service.effective(owner_id=8, role_id="linche") is None
    assert await service.list_versions(owner_id=8, role_id="linche") == []


async def test_role_isolation():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={"name": "临澈"})
    await service.create(owner_id=7, role_id="sudai", base={"name": "苏黛"})
    assert (await service.effective(owner_id=7, role_id="linche")).fields["name"] == "临澈"
    assert (await service.effective(owner_id=7, role_id="sudai")).fields["name"] == "苏黛"


async def test_append_rejects_invalid_changeset_and_leaves_state_untouched():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={"description": "原"})
    with pytest.raises(CardChangeInvalid):
        await service.append_version(owner_id=7, role_id="linche", changes={"system_prompt": "x"})
    assert (await service.effective(owner_id=7, role_id="linche")).fields["description"] == "原"
    assert (await service.list_versions(owner_id=7, role_id="linche"))[-1].version == 1


async def test_rollback_to_unknown_version_is_not_found():
    service, _ = _service()
    await service.create(owner_id=7, role_id="linche", base={})
    with pytest.raises(CardNotFound):
        await service.rollback(owner_id=7, role_id="linche", version=99)


async def test_effective_without_card_returns_none():
    service, _ = _service()
    assert await service.effective(owner_id=7, role_id="nobody") is None
