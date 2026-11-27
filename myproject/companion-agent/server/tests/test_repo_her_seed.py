"""形象资产清单 → 独立 her 注册的库层口径（tools/her_registry + seed_repo_her_packs）。

盘点与 draft-first 纪律（docs/her-inventory-registry-20261128.md）钉在这里：

- **命名一套**：her_id = <renderer>-<asset>，asset 同时是端上 pack_id（D-HID/N10）——
  清单是代码，命名漂移要在 CI 炸，不在部署日志里静默。
- **draft-first（用户裁决 2026-11-28）**：注册一律 draft，published 只由 --accept 验收产生。
- **许可证硬闸**：Unknown（third-party-unreviewed）/ spine / live2d 免费集即使被 --accept
  也必须留在 draft——法律项不是产品验收能豁免的。
- **renderer 词按 DhEngineId 小写对齐**：simple 是纸偶词（不引入 layered），新增 spine/
  talkinghead/vrm。
- **幂等**：重跑不顶 pack_version；验收（draft→published）顶一次版本。
- **不建绑定**：形象注册与角色绑定是两回事（换形象不换人格，换绑归协调）。
"""

import hashlib

import pytest

from companion.service.roles.hers import SqlHerPackStore
from tools.her_registry import (
    ENTRIES,
    LICENSE_VOCAB,
    PRODUCTION_RENDERERS,
    RENDERER_VOCAB,
    HerEntry,
    build_payload,
    license_blocked,
    pack_digest,
    publish_blockers,
    seed_repo_hers,
    validate_entry,
)


def _entry(**over) -> HerEntry:
    base = dict(her_id="simple-unit-test-pack", name="测试", renderer="simple",
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


def test_puppet_word_is_simple_not_layered():
    """用户裁决：renderer 词与 DhEngineId 小写对齐——纸偶是 simple（现网 simple-* 已用），
    不另起 layered。新增词只有 spine/talkinghead/vrm（CharacterEngineType 缺的那三个引擎）。"""
    assert "simple" in RENDERER_VOCAB and "layered" not in RENDERER_VOCAB
    assert {"spine", "talkinghead", "vrm"} <= RENDERER_VOCAB
    assert any(e.her_id == "simple-demo-avatar-v1" for e in ENTRIES)
    assert PRODUCTION_RENDERERS == frozenset({"simple"})


@pytest.mark.parametrize("bad", [
    dict(her_id="live2d-wrong-asset"),          # her_id 与 renderer-asset 拼不上
    dict(renderer="spine2d"),                   # 词表外的新造词
    dict(renderer="layered"),                   # 纸偶词是 simple，layered 不在词表（裁决口径）
    dict(asset="Demo-avatar"),                  # pack_id 大写 → 端上 CharacterAssetPolicy 拒
    dict(license_id="CC0"),                     # 许可证词表外（Unknown 不是自由文本）
    dict(her_id="simple-x", asset="x", version=0),
])
def test_naming_and_vocab_violations_are_refused(bad):
    with pytest.raises(ValueError):
        validate_entry(_entry(**bad))


# ---- 判读信号：三道闸各自独立，写在报告里而非自动落状态 ------------------------

def test_clean_entry_has_no_blockers():
    assert publish_blockers(_entry(), "ab" * 32) == []


def test_unknown_license_is_a_hard_blocker_even_with_hash_and_renderer():
    # 「Unknown 只能标 draft」——许可证闸优先，且是硬闸（验收不能越）。
    e = _entry(license_id="third-party-unreviewed")
    assert license_blocked(e)
    assert any("hard gate" in b for b in publish_blockers(e, "ab" * 32))


def test_lab_renderer_is_a_soft_blocker():
    # CC0 的 vrm/spine/talkinghead：许可可上架，但 release 客户端渲染不了——产品可推进。
    e = _entry(her_id="vrm-unit-test-pack", renderer="vrm", asset="unit-test-pack",
               license_id="cc0-1.0")
    assert not license_blocked(e)
    assert publish_blockers(e, "ab" * 32) == [
        "renderer vrm not client-renderable in release yet"]


def test_missing_pack_hash_is_a_blocker():
    assert publish_blockers(_entry(), None) == [
        "pack file missing (needs --assets-root / T-11 build)"]


def test_spine_sample_license_is_blocked_until_reviewed():
    spine = next(e for e in ENTRIES if e.renderer == "spine")
    assert spine.license_id == "spine-sample-eval"
    assert license_blocked(spine)


# ---- pack_digest：hash 现算，口径=文件本体 sha256 ------------------------------

def test_pack_digest_matches_file_sha256(tmp_path):
    blob = b"zip-bytes-not-real"
    rel = "feature-companion/src/main/assets/avatars/demo-avatar-v1.zip"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(blob)
    e = next(x for x in ENTRIES if x.her_id == "simple-demo-avatar-v1")
    assert e.pack_kind == "zip"
    assert pack_digest(e, tmp_path) == hashlib.sha256(blob).hexdigest()


def test_pack_digest_none_without_root_or_for_build_packs(tmp_path):
    e = next(x for x in ENTRIES if x.her_id == "simple-demo-avatar-v1")
    assert pack_digest(e, None) is None                 # 没给 assets-root
    assert pack_digest(e, tmp_path) is None             # 文件不在（dev cache/引进候选）
    spine = next(x for x in ENTRIES if x.renderer == "spine")
    assert pack_digest(spine, tmp_path) is None         # build 形态：等产线 T-11


# ---- 落库：draft-first、manual、无绑定、幂等 ------------------------------------

async def test_seed_registers_everything_as_draft_by_default(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    first = await seed_repo_hers(store)
    assert len(first) == len(ENTRIES)
    assert {r["her_id"] for r in first} == {e.her_id for e in ENTRIES}
    # draft-first：没有任何一行因为「闸门恰好都过」就自动上架。
    assert all(r["status"] == "draft" for r in first)

    for e in ENTRIES:
        rec = await store.load(e.her_id)
        assert rec is not None and rec.source == "manual" and rec.renderer == e.renderer
        assert rec.status == "draft"
        ref = rec.model_ref
        assert ref["asset"] == e.asset and ref["version"] == e.version
        assert rec.payload["license"]["id"] == e.license_id  # 为什么 draft，行里看得见

    second = await seed_repo_hers(store)             # 重跑（每次部署都跑）不顶版本
    assert [r["pack_version"] for r in second] == [1] * len(second)


async def test_accept_publishes_only_license_clean_rows(sqlite_engine, tmp_path):
    """验收上架：许可证干净的可 published；许可证硬闸的即使 --accept 也留 draft 并说明。"""
    rel = next(x for x in ENTRIES if x.her_id == "simple-demo-avatar-v1").source_paths[0]
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(b"d7af-not-real-but-enough")
    store = SqlHerPackStore(sqlite_engine)
    reports = {r["her_id"]: r for r in await seed_repo_hers(
        store, ENTRIES, tmp_path,
        accept=frozenset({"simple-demo-avatar-v1", "vrm-hairsample-female"}))}

    ok = reports["simple-demo-avatar-v1"]            # own ∧ 纸偶可渲染 ∧ hash 现算
    assert ok["status"] == "published" and ok["note"] == "accepted"
    vrm = reports["vrm-hairsample-female"]           # CC0 许可干净，可验收（renderer 仍 lab）
    assert vrm["status"] == "published"

    rec = await store.load("simple-demo-avatar-v1")
    assert rec is not None and rec.status == "published"
    assert rec.model_ref["hash"] == hashlib.sha256(b"d7af-not-real-but-enough").hexdigest()


async def test_accept_cannot_override_license_hard_gate(sqlite_engine):
    """Unknown license 就算被点名验收也只能 draft——法律项不是产品验收能豁免的。"""
    store = SqlHerPackStore(sqlite_engine)
    reports = {r["her_id"]: r for r in await seed_repo_hers(
        store, ENTRIES, None, accept=frozenset({"spine-spineboy-pro", "live2d-atri"}))}
    for her_id in ("spine-spineboy-pro", "live2d-atri"):
        assert reports[her_id]["status"] == "draft"
        assert reports[her_id]["note"] == "accept refused: license hard gate"


async def test_accept_unknown_her_id_is_rejected(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    with pytest.raises(ValueError):
        await seed_repo_hers(store, ENTRIES, None, accept=frozenset({"simple-nope"}))


async def test_acceptance_bumps_version_once(sqlite_engine, tmp_path):
    """draft→published 是内容变（status 变）：版本号顶一次，对账看得出验收发生过。"""
    rel = next(x for x in ENTRIES if x.her_id == "simple-demo-avatar-v1").source_paths[0]
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(b"bytes")
    store = SqlHerPackStore(sqlite_engine)
    await seed_repo_hers(store, ENTRIES, tmp_path)                       # draft
    reports = {r["her_id"]: r for r in await seed_repo_hers(
        store, ENTRIES, tmp_path, accept=frozenset({"simple-demo-avatar-v1"}))}
    assert reports["simple-demo-avatar-v1"]["pack_version"] == 2


async def test_seed_creates_no_character_bindings(sqlite_engine):
    """形象注册 ≠ 换绑：ca_character_her 归卡播种与协调动作，本脚本一行都不写。"""
    store = SqlHerPackStore(sqlite_engine)
    await seed_repo_hers(store)
    for role in ("linche", "sudai"):
        assert await store.bindings(role) == []


async def test_dev_cache_and_import_candidates_land_draft_with_blockers(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    reports = {r["her_id"]: r for r in await seed_repo_hers(store)}   # 无 assets-root
    for her_id in ("simple-demo-avatar-v1", "vrm-hairsample-female", "talkinghead-mpfb"):
        assert reports[her_id]["status"] == "draft"
        assert reports[her_id]["hash"] is None
        assert any("pack file missing" in b for b in reports[her_id]["blockers"])
    # ChatWaifu 三件套（仅 dev cache、未入库）必须出现在清单里——「GitHub 引入的 model
    # 全部整理成独立 her」这条覆盖到了它们，许可未审所以 draft 锁死。
    for her_id in ("live2d-atri", "live2d-amadeus", "live2d-yuuka"):
        assert reports[her_id]["status"] == "draft"
        assert any("hard gate" in b for b in reports[her_id]["blockers"])


# ---- 播种工具：import 名钉死 + CLI 参数 ----------------------------------------

async def test_seed_tool_imports_resolve(monkeypatch):
    """同 test_her_pack_store 的教训：104 首跑曾因错 import 直接崩。
    数据库地址置空走「缺 URL 返回 2」分支——不碰库，但全部 import 先执行。"""
    from companion.config import settings
    from tools.seed_repo_her_packs import parse_args, seed

    monkeypatch.setattr(settings, "companion_database_url", "")
    monkeypatch.setattr(settings, "companion_db_host", "")
    assert await seed() == 2
    args = parse_args(["--assets-root", "/nonexistent-dir",
                       "--accept", "simple-demo-avatar-v1",
                       "--accept", "live2d-atri"])
    assert str(args.assets_root) == "/nonexistent-dir"
    assert args.accept == ["simple-demo-avatar-v1", "live2d-atri"]


def test_payload_shape_survives_store_validation():
    """payload 必须过 hers.validate_payload（写入口严进）：model_ref 是映射。"""
    from companion.service.roles.hers import validate_payload

    for e in ENTRIES:
        payload = build_payload(e, "cd" * 32)
        validate_payload(payload)
        assert payload["model_ref"] == {"asset": e.asset, "version": e.version,
                                        "hash": "cd" * 32}
        assert "thumbnail" in payload          # 缩略图留位，出图不挡注册
