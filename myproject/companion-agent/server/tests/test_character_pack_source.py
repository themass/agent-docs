"""角色封装进库后的读取链：DB 源、文件兜底、播种工具。

链的口径：``ChainedCharacterSource`` 先读库、未命中再读文件。库是事实源
（部署后播种/改写都落库），文件只是未播种环境的兜底——两条路径必须在同一次
进程里共存，否则没跑过播种的部署会直接把角色页读空。
"""

import json

import pytest

from companion.service.roles.files import CharacterSource
from companion.service.roles.packs import (
    ChainedCharacterSource,
    DbCharacterSource,
    SqlCharacterPackStore,
    renderer_of,
    seed_from_files,
)

SUFFIX = ".v2.json"


def _payload(name: str, renderer: str = "live2d", asset: str = "x-v1") -> dict:
    data: dict = {"name": name, "description": f"{name} 的人设",
                  "voice_ref": {"provider": "volcengine", "voice_id": f"v_{name}"}}
    if renderer:
        data["model_ref"] = {"renderer": renderer, "asset": asset}
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


# ---- renderer_of：技术判别的唯一取法 -----------------------------------------

@pytest.mark.parametrize("model_ref,expected", [
    ({"renderer": "live2d", "asset": "a"}, "live2d"),
    ({"asset": "a"}, ""),          # 没有 renderer 键
    ("default-chat", ""),          # 字符串不是引擎判别，别把它当 renderer 透传
    (None, ""),
])
def test_renderer_of_reads_only_the_discriminator(model_ref, expected):
    card = type("Card", (), {"model_ref": model_ref})()
    assert renderer_of(card) == expected


# ---- DbCharacterSource -------------------------------------------------------

async def test_db_source_loads_a_packed_card(sqlite_engine):
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="linche", payload=_payload("林澈", renderer="simple", asset="linche-v1"),
                       renderer="simple", pack_asset="linche-v1", source="file")
    card = await DbCharacterSource(store).load("linche")
    assert card.name == "林澈"
    assert card.id == "linche"  # 卡里没写 id 时按行补，与文件源同一口径
    assert card.voice_ref["voice_id"] == "v_林澈"


async def test_db_source_missing_raises_file_not_found(sqlite_engine):
    """未命中必须抛 FileNotFoundError——resolver 的「没有这个角色」判据钉的是这个异常。"""
    with pytest.raises(FileNotFoundError):
        await DbCharacterSource(SqlCharacterPackStore(sqlite_engine)).load("ghost")


async def test_db_source_normalizes_the_renderer_column_onto_the_card(sqlite_engine):
    """库里旧卡没写 model_ref 时，判别列补进卡，目录与引擎选择只认卡一条路。"""
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="sudai", payload=_payload("苏黛", renderer=""),
                       renderer="vrm", pack_asset="sudai-v1", source="file")
    card = await DbCharacterSource(store).load("sudai")
    assert renderer_of(card) == "vrm"


async def test_db_cards_lists_every_sealed_role(sqlite_engine):
    store = SqlCharacterPackStore(sqlite_engine)
    for role_id in ("linche", "sudai"):
        await store.upsert(role_id=role_id, payload=_payload(role_id),
                           renderer="simple", pack_asset=f"{role_id}-v1", source="file")
    cards = await DbCharacterSource(store).cards()
    assert sorted(cards) == ["linche", "sudai"]


# ---- ChainedCharacterSource：库优先、文件兜底 ---------------------------------

def _file_source(tmp_path, by_id: dict[str, str]):
    for role_id, name in by_id.items():
        (tmp_path / f"{role_id}{SUFFIX}").write_text(json.dumps(_payload(name), ensure_ascii=False),
                                                     encoding="utf-8")
    return CharacterSource(tmp_path)


async def test_chain_prefers_the_database_over_the_file(sqlite_engine, tmp_path):
    files = _file_source(tmp_path, {"linche": "文件版"})
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="linche", payload=_payload("库里版"),
                       renderer="simple", pack_asset="linche-v1", source="file")
    chain = ChainedCharacterSource((DbCharacterSource(store), files))
    assert (await chain.load("linche")).name == "库里版"


async def test_chain_falls_back_to_files_when_the_database_is_empty(sqlite_engine, tmp_path):
    chain = ChainedCharacterSource((DbCharacterSource(SqlCharacterPackStore(sqlite_engine)),
                                    _file_source(tmp_path, {"linche": "文件版"})))
    assert (await chain.load("linche")).name == "文件版"


async def test_chain_merges_both_for_the_catalog(sqlite_engine, tmp_path):
    """列表页要同时看见库里已封装的和还没播种的——迁移期不能二选一。"""
    files = _file_source(tmp_path, {"onlyfile": "文件角色"})
    store = SqlCharacterPackStore(sqlite_engine)
    await store.upsert(role_id="linche", payload=_payload("库里版"),
                       renderer="simple", pack_asset="linche-v1", source="file")
    cards = await ChainedCharacterSource((DbCharacterSource(store), files)).cards()
    assert sorted(cards) == ["linche", "onlyfile"]
    assert cards["linche"].name == "库里版"


# ---- 播种工具 -----------------------------------------------------------------

async def test_seed_from_files_imports_every_card_with_its_discriminator(sqlite_engine, tmp_path):
    _file_source(tmp_path, {"linche": "林澈", "sudai": "苏黛"})
    store = SqlCharacterPackStore(sqlite_engine)
    seeded = await seed_from_files(store, tmp_path)
    assert sorted(seeded) == ["linche", "sudai"]
    records = {r.role_id: r for r in await store.list_records()}
    assert records["linche"].renderer == "live2d"      # 从卡里的 model_ref 提取
    assert records["linche"].pack_asset == "x-v1"


async def test_seed_is_idempotent_when_nothing_changed(sqlite_engine, tmp_path):
    """部署会反复跑播种；内容没变就不该把 pack_version 一直往上顶。"""
    _file_source(tmp_path, {"linche": "林澈"})
    store = SqlCharacterPackStore(sqlite_engine)
    await seed_from_files(store, tmp_path)
    await seed_from_files(store, tmp_path)
    assert (await store.load("linche")).pack_version == 1


async def test_seed_bumps_the_version_when_content_changed(sqlite_engine, tmp_path):
    _file_source(tmp_path, {"linche": "林澈"})
    store = SqlCharacterPackStore(sqlite_engine)
    await seed_from_files(store, tmp_path)
    (tmp_path / f"linche{SUFFIX}").write_text(json.dumps(_payload("林澈 v2"), ensure_ascii=False),
                                              encoding="utf-8")
    await seed_from_files(store, tmp_path)
    rec = await store.load("linche")
    assert rec.pack_version == 2
    assert rec.card.name == "林澈 v2"


async def test_seed_skips_a_broken_file_without_failing_the_run(sqlite_engine, tmp_path):
    (tmp_path / f"good{SUFFIX}").write_text(json.dumps(_payload("好卡"), ensure_ascii=False), encoding="utf-8")
    (tmp_path / f"bad{SUFFIX}").write_text("{ not json", encoding="utf-8")
    seeded = await seed_from_files(SqlCharacterPackStore(sqlite_engine), tmp_path)
    assert seeded == ["good"]
