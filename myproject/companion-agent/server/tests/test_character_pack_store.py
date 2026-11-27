"""ca_character_pack 的 SQL store（角色封装进数据库的第一层）。

约定与 ca_role_card 的 store 一致：单语句读写、读写往返在同一内存 SQLite 上跑。
这张表是「系统角色包」：随包发布的角色卡播种进来，之后运行时（提示词、目录、
音色）都以它为准；文件只留作未播种环境的兜底。
"""

import pytest

from companion.service.roles.packs import SqlCharacterPackStore


def _payload(role_id: str, name: str) -> dict:
    return {
        "spec": "chara_card_v2", "spec_version": "2.0",
        "data": {
            "name": name,
            "description": f"{name} 的人设",
            "voice_ref": {"provider": "volcengine", "voice_id": f"v_{role_id}"},
            "model_ref": {"renderer": "live2d", "asset": f"{role_id}-v1"},
        },
    }


async def test_upsert_then_load_roundtrip(sqlite_engine):
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="linche", payload=_payload("linche", "林澈"),
                       renderer="simple", pack_asset="linche-v1", source="file")
    rec = await store.load("linche")
    assert rec is not None
    assert rec.role_id == "linche"
    assert rec.card.name == "林澈"
    assert rec.card.description == "林澈 的人设"
    assert rec.card.voice_ref["voice_id"] == "v_linche"
    assert rec.renderer == "simple"
    assert rec.pack_asset == "linche-v1"


async def test_unknown_role_loads_none(sqlite_engine):
    assert await SqlCharacterPackStore(sqlite_engine).load("ghost") is None


async def test_upsert_twice_keeps_one_row_and_bumps_version(sqlite_engine):
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="linche", payload=_payload("linche", "林澈"),
                       renderer="simple", pack_asset="linche-v1", source="file")
    await store.upsert(role_id="linche", payload=_payload("linche", "林澈（改）"),
                       renderer="live2d", pack_asset="linche-v2", source="file")
    rec = await store.load("linche")
    assert rec.card.name == "林澈（改）"
    assert rec.renderer == "live2d"
    assert rec.pack_asset == "linche-v2"
    assert rec.pack_version == 2
    records = await store.list_records()
    assert [r.role_id for r in records] == ["linche"]


async def test_list_records_sorted_by_role_id(sqlite_engine):
    store = SqlCharacterPackStore(sqlite_engine)
    for role_id in ("sudai", "linche"):
        await store.upsert(role_id=role_id, payload=_payload(role_id, role_id),
                           renderer="simple", pack_asset=f"{role_id}-v1", source="file")
    assert [r.role_id for r in await store.list_records()] == ["linche", "sudai"]


async def test_broken_row_does_not_raise(sqlite_engine):
    """库里存进一张坏卡（缺 data 块）时 load 给 None、list 跳过它，不是异常。

    角色是发布资产：解析失败要让调用方退回兜底（文件或默认），不能让回合/房间连坐。
    坏行只能来自库内手改或半截写入——写入口自己会拒（见下一条）。
    """
    from sqlalchemy import insert

    from companion.db.schema import character_pack

    async with sqlite_engine.begin() as conn:
        await conn.execute(insert(character_pack).values(
            role_id="broken", payload={"spec": "chara_card_v2"}, renderer="", pack_asset="",
            pack_version=1, source="manual"))
    store = SqlCharacterPackStore(sqlite_engine)
    assert await store.load("broken") is None
    assert await store.list_records() == []


async def test_upsert_rejects_a_payload_that_is_not_a_card(sqlite_engine):
    """写入口严进：解析不出卡的 payload 当场拒，别让坏数据进库后靠读路径兜底。"""
    with pytest.raises(ValueError):
        await SqlCharacterPackStore(sqlite_engine).upsert(
            role_id="broken", payload={"spec": "chara_card_v2"},
            renderer="", pack_asset="", source="file")
