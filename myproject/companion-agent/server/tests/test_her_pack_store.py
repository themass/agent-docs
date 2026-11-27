"""her 包注册表的读写与绑定（ca_her_pack / ca_character_her）。

persona/her 分层第一刀的库层口径（docs/design/2026-11-28-persona-her-split-architecture.md §3）：
- upsert 幂等：内容没变不写、不顶 pack_version；payload / status / renderer 任一变了 +1
  （规则同 packs.py——播种会反复跑，版本号是对账信号，不是计数器）。
- 写入口严进：payload 结构不合法当场拒；读路径宽出：库内坏行只是跳过，列表页不连坐。
- 绑定默认一对一，重复绑定幂等；解析取 is_default，多条默认取 her_id 最小的一条（稳定）。
"""

import pytest

from companion.service.roles.hers import (
    HerPayloadError,
    SqlHerPackStore,
    validate_payload,
)


def _payload(name="林澈·夏日", asset="linche-summer-v1", **extra) -> dict:
    data = {
        "name": name,
        "tagline": "海边的她",
        "model_ref": {"asset": asset, "version": 1, "hash": "ab" * 32},
        "effects": [{"id": "fx_wave", "anchor": "head"}],
        "stickers": [],
        "thumbnail": "https://cdn/thumb.webp",
    }
    data.update(extra)
    return data


# ---- 结构校验 ----------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    None, "string", ["list"],
    {"model_ref": "legacy-string"},          # 字符串 model_ref 不是合法呈现声明
    {"effects": "fx_wave"},                  # 目录必须是列表
])
def test_validate_payload_rejects_half_written_shapes(bad):
    with pytest.raises(HerPayloadError):
        validate_payload(bad)


# ---- upsert 幂等与版本对账 ----------------------------------------------------

async def test_first_upsert_starts_at_version_one(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    rec = await store.upsert(her_id="live2d-linche-summer", renderer="live2d",
                             payload=_payload(), status="published", source="card")
    assert rec.pack_version == 1
    again = await store.load("live2d-linche-summer")
    assert again is not None and again.renderer == "live2d" and again.status == "published"


async def test_reseeding_identical_content_does_not_bump_version(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await store.upsert(her_id="h1", renderer="simple", payload=_payload(),
                       status="published", source="card")
    rec = await store.upsert(her_id="h1", renderer="simple", payload=_payload(),
                             status="published", source="card")
    assert rec.pack_version == 1


async def test_payload_status_or_renderer_change_bumps_once_each(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await store.upsert(her_id="h1", renderer="simple", payload=_payload(),
                       status="draft", source="card")
    bumped = await store.upsert(her_id="h1", renderer="simple",
                                payload=_payload(tagline="换了标语"), status="draft", source="card")
    assert bumped.pack_version == 2
    published = await store.upsert(her_id="h1", renderer="simple",
                                   payload=_payload(tagline="换了标语"),
                                   status="published", source="card")
    # status 变必须是内容变：上线/撤回要在版本号上看得见，不能保持原值。
    assert published.pack_version == 3 and published.status == "published"
    retired = await store.upsert(her_id="h1", renderer="rive",
                                 payload=_payload(tagline="换了标语"),
                                 status="published", source="card")
    assert retired.pack_version == 4 and retired.renderer == "rive"


async def test_bad_payload_is_refused_at_the_write_door(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    with pytest.raises(HerPayloadError):
        await store.upsert(her_id="h1", renderer="simple", payload={"model_ref": "oops"},
                           status="draft", source="card")
    assert await store.load("h1") is None


async def test_unknown_status_is_refused(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    with pytest.raises(ValueError):
        await store.upsert(her_id="h1", renderer="simple", payload=_payload(),
                           status="published_retired", source="card")


async def test_corrupt_row_is_skipped_in_listing(sqlite_engine):
    """写入口严进之后的读路径宽出：库内手改出的坏行不让列表页连坐。"""
    from sqlalchemy import insert, update
    from companion.db.schema import her_pack
    from datetime import UTC, datetime

    store = SqlHerPackStore(sqlite_engine)
    await store.upsert(her_id="good", renderer="simple", payload=_payload(),
                       status="published", source="card")
    now = datetime.now(UTC)
    async with store._engine.begin() as conn:  # 模拟库内手改：payload 变成非法标量
        await conn.execute(insert(her_pack).values(
            her_id="bad", renderer="simple", payload={"effects": "not-a-list"},
            status="published", source="manual", pack_version=1, created_at=now, updated_at=now))
        await conn.execute(update(her_pack).where(her_pack.c.her_id == "bad")
                           .values(payload="broken"))
    listed = await store.list_records()
    assert [r.her_id for r in listed] == ["good"]


# ---- 绑定 --------------------------------------------------------------------

async def test_bind_is_idempotent_and_default_resolves(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await store.bind(role_id="linche", her_id="live2d-linche-v1")
    await store.bind(role_id="linche", her_id="live2d-linche-v1")
    assert await store.default_her_id("linche") == "live2d-linche-v1"
    assert len(await store.bindings("linche")) == 1


async def test_multiple_defaults_resolve_stably_to_lowest_id(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await store.bind(role_id="linche", her_id="b-second")
    await store.bind(role_id="linche", her_id="a-first")
    assert await store.default_her_id("linche") == "a-first"


async def test_unbound_role_has_no_default(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    assert await store.default_her_id("ghost") is None


# ---- seed_from_cards：角色卡 → 呈现实体的桥 -----------------------------------

def _card(name: str, model_ref, voice_ref=None) -> dict:
    data = {"name": name, "description": "一个人。"}
    if model_ref is not None:
        data["model_ref"] = model_ref
    if voice_ref is not None:
        data["voice_ref"] = voice_ref
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


async def test_seed_from_cards_creates_packs_and_default_bindings(sqlite_engine):
    from companion.agent.roles.card import from_v2_json
    from companion.service.roles.hers import seed_from_cards

    cards = {
        "linche": from_v2_json(_card("林澈", {"renderer": "live2d", "asset": "linche-v1"},
                                     {"provider": "volcengine", "voice_id": "v_linche"})),
        "sudai": from_v2_json(_card("苏黛", {"renderer": "simple", "asset": "sudai-v1"})),
        # 字符串 model_ref 是历史模型路由标签，不是呈现声明：跳过（renderer_of 同口径）。
        "legacy": from_v2_json(_card("旧卡", "default-chat")),
    }
    seeded, skipped = await seed_from_cards(SqlHerPackStore(sqlite_engine), cards)
    assert sorted(seeded) == ["linche->live2d-linche-v1", "sudai->simple-sudai-v1"]
    assert skipped == ["legacy"]

    store = SqlHerPackStore(sqlite_engine)
    assert await store.default_her_id("linche") == "live2d-linche-v1"
    pack = await store.load("live2d-linche-v1")
    assert pack is not None and pack.status == "published" and pack.source == "card"
    assert pack.voice_ref["voice_id"] == "v_linche"
    # 重跑不顶版本（播种会在每次部署跑）。
    await seed_from_cards(store, cards)
    again = await store.load("live2d-linche-v1")
    assert again is not None and again.pack_version == 1


async def test_seed_tool_imports_resolve(monkeypatch):
    """播种工具不在 HTTP/库测试覆盖里，104 首跑曾因错 import 直接崩
    （companion.agent.roles.files 不存在，应为 service.roles.files）。
    这里把数据库地址置空后调用 seed()：函数体顶部的全部 import 先执行，
    然后走「缺 DATABASE_URL 返回 2」的分支——不碰任何库，但 import 名钉死。
    """
    from companion.config import settings
    from tools.seed_her_packs import seed

    # database_url 是算出来的属性：整串与拆键都置空才会得到空串。
    monkeypatch.setattr(settings, "companion_database_url", "")
    monkeypatch.setattr(settings, "companion_db_host", "")
    assert await seed() == 2
