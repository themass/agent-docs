"""形象资产清单 → 独立 her 注册的库层口径（tools/her_registry + seed_repo_her_packs）。

盘点纪律（docs/her-inventory-registry-20261128.md）钉在这里：

- **命名一套**：her_id = <renderer>-<asset>，asset 同时是端上 pack_id（D-HID/N10）——
  清单是代码，命名漂移要在 CI 炸，不在部署日志里静默。
- **三道闸**（许可证 ∧ renderer ∧ pack hash）全过才 published；Unknown（
  third-party-unreviewed）哪怕其余全过也必须是 draft——「Unknown 只能标 draft」。
- **幂等**：重跑不顶 pack_version（播种每次部署都跑）。
- **不建绑定**：形象注册与角色绑定是两回事（换形象不换人格，换绑归协调）。
"""

import hashlib

import pytest

from companion.service.roles.hers import SqlHerPackStore
from tools.her_registry import (
    ENTRIES,
    LICENSE_VOCAB,
    RENDERER_VOCAB,
    HerEntry,
    block_reason,
    build_payload,
    decide_status,
    pack_digest,
    seed_repo_hers,
    validate_entry,
)


def _entry(**over) -> HerEntry:
    base = dict(her_id="layered-unit-test-pack", name="测试", renderer="layered",
                asset="unit-test-pack", version=1, license_id="own", origin="test",
                pack_kind="zip")
    base.update(over)
    return HerEntry(**base)


# ---- 清单本身是代码：纪律在 CI 钉死 -------------------------------------------

def test_every_entry_follows_her_id_and_vocab_discipline():
    seen = set()
    for e in ENTRIES:
        validate_entry(e)                       # her_id == <renderer>-<asset>，两段各自合法
        assert e.renderer in RENDERER_VOCAB and e.license_id in LICENSE_VOCAB
        assert e.her_id not in seen, f"duplicate her_id: {e.her_id}"
        seen.add(e.her_id)


@pytest.mark.parametrize("bad", [
    dict(her_id="live2d-wrong-asset"),          # her_id 与 renderer-asset 拼不上
    dict(renderer="spine2d"),                   # 词表外的新造词
    dict(asset="Demo-avatar"),                  # pack_id 大写 → 端上 CharacterAssetPolicy 拒
    dict(license_id="CC0"),                     # 许可证词表外（Unknown 不是自由文本）
    dict(her_id="layered-x", asset="x", version=0),
])
def test_naming_and_vocab_violations_are_refused(bad):
    with pytest.raises(ValueError):
        validate_entry(_entry(**bad))


# ---- 三道闸：状态判定纯函数 ---------------------------------------------------

def test_all_gates_pass_published():
    e = _entry()
    assert decide_status(e, "ab" * 32) == "published"


def test_unknown_license_draft_even_with_hash_and_production_renderer():
    # 「Unknown license 落 draft」——许可闸优先于一切。
    e = _entry(license_id="third-party-unreviewed")
    assert decide_status(e, "ab" * 32) == "draft"
    assert "license" in block_reason(e, "ab" * 32)


def test_lab_renderer_draft_even_cc0_and_hashed():
    # CC0 的 vrm/spine/talkinghead 是登记实体，不是上架：引擎还在 lab。
    e = _entry(her_id="vrm-unit-test-pack", renderer="vrm", asset="unit-test-pack",
               license_id="cc0-1.0")
    assert decide_status(e, "ab" * 32) == "draft"
    assert "renderer" in block_reason(e, "ab" * 32)


def test_missing_pack_hash_blocks_publish():
    e = _entry()
    assert decide_status(e, None) == "draft"
    assert "pack file" in block_reason(e, None)


def test_spine_sample_license_is_permanently_draft_until_reviewed():
    spine = next(e for e in ENTRIES if e.renderer == "spine")
    assert spine.license_id == "spine-sample-eval"
    assert decide_status(spine, "ab" * 32) == "draft"


# ---- pack_digest：hash 现算，口径=文件本体 sha256 ------------------------------

def test_pack_digest_matches_file_sha256(tmp_path):
    blob = b"zip-bytes-not-real"
    rel = "feature-companion/src/main/assets/avatars/demo-avatar-v1.zip"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(blob)
    e = ENTRIES[0]
    assert e.her_id == "layered-demo-avatar-v1" and e.pack_kind == "zip"
    assert pack_digest(e, tmp_path) == hashlib.sha256(blob).hexdigest()


def test_pack_digest_none_without_root_or_for_build_packs(tmp_path):
    e = ENTRIES[0]
    assert pack_digest(e, None) is None                 # 没给 assets-root
    assert pack_digest(e, tmp_path) is None             # 文件不在（dev cache/引进候选）
    spine = next(x for x in ENTRIES if x.renderer == "spine")
    assert pack_digest(spine, tmp_path) is None         # build 形态：等产线 T-11


# ---- 落库：幂等、manual、无绑定、报告可读 --------------------------------------

async def test_seed_registers_inventory_as_manual_and_is_idempotent(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    first = await seed_repo_hers(store)
    assert len(first) == len(ENTRIES)
    assert {r["her_id"] for r in first} == {e.her_id for e in ENTRIES}

    for e in ENTRIES:                                # 每一行都进来了，source=manual
        rec = await store.load(e.her_id)
        assert rec is not None and rec.source == "manual" and rec.renderer == e.renderer
        assert rec.status in ("draft", "published")
        ref = rec.model_ref
        assert ref["asset"] == e.asset and ref["version"] == e.version
        assert "hash" in ref or rec.status == "draft"  # 没 hash 就不可能 published

    second = await seed_repo_hers(store)             # 重跑（每次部署都跑）不顶版本
    assert [r["pack_version"] for r in second] == [1] * len(second)


async def test_seed_creates_no_character_bindings(sqlite_engine):
    """形象注册 ≠ 换绑：ca_character_her 归卡播种与协调动作，本脚本一行都不写。"""
    store = SqlHerPackStore(sqlite_engine)
    await seed_repo_hers(store)
    for role in ("linche", "sudai"):
        assert await store.bindings(role) == []


async def test_untracked_or_dev_cache_assets_land_draft_with_reason(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    reports = {r["her_id"]: r for r in await seed_repo_hers(store)}   # 无 assets-root
    for her_id in ("layered-demo-avatar-v1", "vrm-hairsample-female", "talkinghead-mpfb"):
        assert reports[her_id]["status"] == "draft"
        assert reports[her_id]["hash"] is None
    for e in ENTRIES:                                # 每条 draft 都要能回答为什么
        if reports[e.her_id]["status"] == "draft":
            assert reports[e.her_id]["reason"] != "published"


async def test_demo_puppet_publishes_when_pack_file_is_available(sqlite_engine, tmp_path):
    """唯一能全过三道闸的内置形象：给了 assets-root + 文件在 → published + hash。"""
    blob = b"d7af-not-real-but-enough"
    rel = ENTRIES[0].source_paths[0]
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(blob)
    store = SqlHerPackStore(sqlite_engine)
    reports = {r["her_id"]: r for r in await seed_repo_hers(store, ENTRIES, tmp_path)}
    r = reports["layered-demo-avatar-v1"]
    assert r["status"] == "published" and r["hash"] == hashlib.sha256(blob).hexdigest()

    rec = await store.load("layered-demo-avatar-v1")
    assert rec is not None and rec.status == "published"
    assert rec.model_ref["hash"] == hashlib.sha256(blob).hexdigest()
    assert rec.payload["license"]["id"] == "own"     # 为什么 draft/为什么上架，行里看得见


async def test_changed_asset_bumps_version_once(sqlite_engine, tmp_path):
    """hash 变了 = 内容变了：版本号是对账信号（packs 同一口径）。"""
    rel = ENTRIES[0].source_paths[0]
    (tmp_path / rel).parent.mkdir(parents=True)
    store = SqlHerPackStore(sqlite_engine)
    (tmp_path / rel).write_bytes(b"v1-bytes")
    await seed_repo_hers(store, ENTRIES, tmp_path)
    (tmp_path / rel).write_bytes(b"v2-bytes")
    reports = {r["her_id"]: r for r in await seed_repo_hers(store, ENTRIES, tmp_path)}
    assert reports["layered-demo-avatar-v1"]["pack_version"] == 2


# ---- 播种工具：import 名钉死 + 静态筛选 ----------------------------------------

async def test_seed_tool_imports_resolve(monkeypatch):
    """同 test_her_pack_store 的教训：104 首跑曾因错 import 直接崩。
    数据库地址置空走「缺 URL 返回 2」分支——不碰库，但全部 import 先执行。"""
    from companion.config import settings
    from tools.seed_repo_her_packs import parse_args, seed

    monkeypatch.setattr(settings, "companion_database_url", "")
    monkeypatch.setattr(settings, "companion_db_host", "")
    assert await seed() == 2
    args = parse_args(["--assets-root", "/nonexistent-dir", "--status", "draft"])
    assert str(args.assets_root) == "/nonexistent-dir" and args.status == "draft"


def test_status_filter_is_static_gates_only():
    """--status published 只筛静态两道闸（许可/renderer）；pack hash 在运行时判。"""
    from tools.seed_repo_her_packs import seed  # noqa: F401（import 路径钉死）
    from tools.her_registry import PRODUCTION_RENDERERS, PUBLISHABLE_LICENSES

    static_publishable = {e.her_id for e in ENTRIES
                          if e.license_id in PUBLISHABLE_LICENSES
                          and e.renderer in PRODUCTION_RENDERERS}
    assert static_publishable == {"layered-demo-avatar-v1"}


def test_payload_shape_survives_store_validation():
    """payload 必须过 hers.validate_payload（写入口严进）：model_ref 是映射。"""
    from companion.service.roles.hers import validate_payload

    for e in ENTRIES:
        payload = build_payload(e, "cd" * 32)
        validate_payload(payload)
        assert payload["model_ref"] == {"asset": e.asset, "version": e.version,
                                        "hash": "cd" * 32}
        assert "thumbnail" in payload          # 缩略图留位，出图不挡注册
