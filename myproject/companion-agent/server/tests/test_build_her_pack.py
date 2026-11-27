"""Hermes M0「数据面演练」（hermes-her-production-design-20261128.md §7-M0）。

意义：证「产线产物契约 ↔ 端上安装」之间没有未验证假设——build_asset_pack →
validate_asset_pack（G-A 门，Python 镜像端上 CharacterAssetPolicy）→
upsert(source="manual") → bind → HerCatalog.invalidate 一条链在 sqlite 上真走通。

契约的权威来源是端上代码（Android 仓库 weifu-refactor 线，commit 5c951543）：
- feature-companion/src/main/java/com/openapi/ks/myapp/avatar/CharacterAssetPack.kt
  · CharacterAssetManifest.parse 读且只读六个字段：schema_version, pack_id,
    version, engine, entry_point, files（path→sha256）
  · CharacterAssetPolicy 的拒绝点：schema_version==1、pack_id 正则、version>0、
    files 1..200、entry_point ∈ files、路径分量正则且无 . / ..、sha 为 64 位 hex、
    安装总量 ≤100MB
  · CharacterEngineType 枚举 = LAYERED, LIVE2D, RIVE, DUIX, TAO（**无 VRM**，F-ENGINE-ENUM）
- feature-companion/src/main/java/com/openapi/ks/myapp/avatar/AvatarSync.kt
  · 包下载 URL 的既有字段名是 download_url（"o.optString(\"download_url\")"）
- docs/design/2026-11-28-persona-her-split-architecture.md §3
  · payload.model_ref 收敛形态 {asset, version, hash}

下面的 SNAPSHOT 常量就是这份清单的字面量：端上契约变了、或脚本偷偷多了/少了字段，
这两组断言必须先红。
"""

import hashlib
import io
import json
import zipfile

import pytest

from companion.api.http.routers.hers import HerCatalog
from companion.service.roles.hers import SqlHerPackStore
from tools.build_her_pack import (
    ASSET_MANIFEST_FIELDS,
    ENGINE_TYPES,
    MODEL_REF_FIELDS,
    AssetPackError,
    build_asset_pack,
    build_her_payload,
    build,
    deploy_pack,
    validate_asset_pack,
)

# ---- 契约快照：钉死端上清单（改这里 = 改端上契约，必须同步两处） ----------------

def test_client_contract_snapshot_manifest_fields():
    # CharacterAssetManifest.parse（CharacterAssetPack.kt:23-31）读且只读这六个键。
    assert ASSET_MANIFEST_FIELDS == {
        "schema_version", "pack_id", "version", "engine", "entry_point", "files",
    }


def test_client_contract_snapshot_engine_enum():
    # CharacterEngineType（CharacterAssetPack.kt:11）。没有 VRM——产线出 VRM 包前
    # 端上第二刀必须先扩枚举（设计文档待决 Q2）。
    assert ENGINE_TYPES == ("LAYERED", "LIVE2D", "RIVE", "DUIX", "TAO")


def test_client_contract_snapshot_model_ref_fields():
    # persona/her 分层 §3 的 {asset, version, hash} + 下载字段沿用端上既有口径
    # download_url（AvatarSync.kt:68）。URL 落点（生产 CDN）归协调会话，字段名归契约。
    assert MODEL_REF_FIELDS == {"asset", "version", "hash", "download_url"}


# ---- 组装：产物 manifest 必须是端上 parse 能吃的形状 -----------------------------

def _files() -> dict[str, bytes]:
    """最小实验包文件树：内层引擎 manifest（LAYERED 的 manifest.json）+ 两张图层。"""
    inner = {"id": "linche-layers-v1", "canvas": {"w": 512, "h": 768},
             "layers": [{"id": "body", "path": "layers/body.png", "z": 0},
                        {"id": "hair_front", "path": "layers/hair_front.png", "z": 10}]}
    return {
        "manifest.json": json.dumps(inner, ensure_ascii=False).encode(),
        "layers/body.png": b"\x89PNG\r\n\x1a\n fake body layer for contract drill",
        "layers/hair_front.png": b"\x89PNG\r\n\x1a\n fake hair layer",
    }


def _build(**over):
    opts = {"files": _files(), "pack_id": "linche-layers-v1", "version": 1,
            "renderer": "layered", "entry_point": "manifest.json"}
    opts.update(over)
    return build_asset_pack(**opts)


def test_built_manifest_is_exactly_what_client_parse_reads():
    manifest, zip_bytes = _build()
    assert set(manifest) == ASSET_MANIFEST_FIELDS          # 没有多余键，没有缺键
    assert manifest["schema_version"] == 1
    assert manifest["pack_id"] == "linche-layers-v1"
    assert manifest["version"] == 1
    assert manifest["engine"] in ENGINE_TYPES
    assert manifest["entry_point"] in manifest["files"]
    assert set(manifest["files"]) == set(_files())
    assert zip_bytes  # 有产物


def test_manifest_declares_per_file_sha256_of_the_actual_bytes():
    manifest, _ = _build()
    for path, blob in _files().items():
        assert manifest["files"][path] == hashlib.sha256(blob).hexdigest()


def test_zip_matches_manifest_and_is_deterministic():
    manifest_a, zip_a = _build()
    manifest_b, zip_b = _build()
    assert zip_a == zip_b                       # 同输入+版本 → 同字节（T-11 语义）
    with zipfile.ZipFile(io.BytesIO(zip_a)) as zf:
        names = set(zf.namelist())
        assert names == set(manifest_a["files"]) | {"pack-manifest.json"}
        for path, sha in manifest_a["files"].items():
            assert hashlib.sha256(zf.read(path)).hexdigest() == sha
        # 外契约 manifest 也在包里（工具/人查验用），但不在 files 清单里——
        # 端上安装只按 files 落文件，manifest 由调用方（/v1/hers 详情链）供。
        assert json.loads(zf.read("pack-manifest.json")) == manifest_a


# ---- G-A 门：镜像 CharacterAssetPolicy 的每一个拒点 ------------------------------

def test_valid_manifest_passes_the_gate():
    manifest, _ = _build()
    assert validate_asset_pack(manifest) == []


@pytest.mark.parametrize("mutate, needle", [
    (lambda m: m.update(schema_version=2), "schema_version"),
    (lambda m: m.update(pack_id="../hero"), "pack_id"),
    (lambda m: m.update(version=0), "version"),
    (lambda m: m.update(entry_point="missing.json"), "entry_point"),
    (lambda m: m.update(engine="VRM"), "engine"),          # 端上 valueOf 会崩，门先拦
    (lambda m: m["files"].update({"../escape.bin": "ab" * 32}), "path"),
    (lambda m: m["files"].update({"/absolute.bin": "ab" * 32}), "path"),
    (lambda m: m["files"].update({"a\\b.bin": "ab" * 32}), "path"),
    (lambda m: m["files"].update({"good.bin": "not-hex"}), "hash"),
])
def test_gate_rejects_every_point_the_client_would_reject(mutate, needle):
    manifest, _ = _build()
    mutate(manifest)
    violations = validate_asset_pack(manifest)
    assert violations, "端上必拒的包必须在这里就拦下（G-A 硬门）"
    assert any(needle in v for v in violations)


def test_gate_rejects_empty_and_oversized_file_lists():
    manifest, _ = _build()
    manifest["files"] = {}
    assert validate_asset_pack(manifest)
    manifest, _ = _build()
    manifest["files"] = {f"layer{i}.png": "ab" * 32 for i in range(201)}
    manifest["entry_point"] = "layer0.png"
    assert any("200" in v for v in validate_asset_pack(manifest))


def test_build_refuses_bad_tree_before_producing_anything():
    # entry_point 不在文件树里：build 阶段就抛，不出包。
    with pytest.raises(AssetPackError):
        _build(entry_point="nope.json")
    # 路径越界的素材根本进不了包。
    with pytest.raises(AssetPackError):
        _build(files={"../evil.png": b"x"})


# ---- payload：model_ref 与端上契约字段一致 ---------------------------------------

def test_payload_model_ref_locks_to_client_contract():
    manifest, zip_bytes = _build()
    payload = build_her_payload(name="林澈·分层实验", tagline="M0 演练",
                                pack_id="linche-layers-v1", version=1,
                                pack_sha256=hashlib.sha256(zip_bytes).hexdigest(),
                                cdn_base="https://cdn.invalid")
    assert set(payload["model_ref"]) == MODEL_REF_FIELDS
    ref = payload["model_ref"]
    # N10：asset 名 = pack_id，her_id = <renderer>-<asset>，三处不得漂移。
    assert ref["asset"] == manifest["pack_id"] == "linche-layers-v1"
    assert ref["version"] == manifest["version"] == 1
    assert ref["hash"] == hashlib.sha256(zip_bytes).hexdigest()
    assert ref["download_url"].startswith("https://cdn.invalid/")
    assert "linche-layers-v1" in ref["download_url"] and "v1" in ref["download_url"]


# ---- 完整链：sqlite 上首建 v1、重跑版本不动、坏 manifest 不落库 ------------------

async def _deploy(sqlite_engine, tmp_path, **over):
    opts = {"role_id": "linche", "renderer": "layered", "pack_id": "linche-layers-v1",
            "version": 1, "name": "林澈·分层实验", "tagline": "M0 演练",
            "files": _files(), "entry_point": "manifest.json",
            "cdn_base": "https://cdn.invalid", "out_dir": tmp_path}
    opts.update(over)
    return await deploy_pack(SqlHerPackStore(sqlite_engine), **opts)


async def test_deploy_creates_v1_published_manual_and_default_binding(sqlite_engine, tmp_path):
    rec = await _deploy(sqlite_engine, tmp_path)
    assert rec.her_id == "layered-linche-layers-v1"      # D-HID：<renderer>-<asset>
    assert rec.pack_version == 1
    assert rec.status == "published" and rec.source == "manual"   # N12：M0 用 manual
    store = SqlHerPackStore(sqlite_engine)
    assert await store.default_her_id("linche") == rec.her_id

    # /v1/hers 可见（HerCatalog 已 invalidate，读的是库）。
    catalog = HerCatalog(store)
    catalog.invalidate()
    items, total = await catalog.list()
    assert total == 1 and items[0].id == rec.her_id
    detail = await catalog.get(rec.her_id)
    assert detail.model_ref["asset"] == "linche-layers-v1"
    assert detail.model_ref["hash"] == rec.payload["model_ref"]["hash"]


async def test_deploy_rerun_does_not_bump_pack_version(sqlite_engine, tmp_path):
    store = SqlHerPackStore(sqlite_engine)
    first = await _deploy(sqlite_engine, tmp_path)
    again = await _deploy(sqlite_engine, tmp_path)
    assert first.pack_version == 1 and again.pack_version == 1
    assert (await store.load("layered-linche-layers-v1")).pack_version == 1


async def test_manifest_violation_never_reaches_the_db(sqlite_engine, tmp_path):
    with pytest.raises(AssetPackError):
        await _deploy(sqlite_engine, tmp_path, entry_point="not-in-tree.json")
    assert await SqlHerPackStore(sqlite_engine).load("layered-linche-layers-v1") is None


async def test_deploy_writes_the_pack_zip_into_out_dir(sqlite_engine, tmp_path):
    await _deploy(sqlite_engine, tmp_path)
    zip_path = tmp_path / "linche-layers-v1-v1.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        assert "pack-manifest.json" in zf.namelist()


# ---- 脚本形态：import 名钉死 + 缺 DATABASE_URL 返回 2（同 seed_her_packs 的教训）--

async def test_build_tool_imports_resolve_without_db(monkeypatch, tmp_path):
    from companion.config import settings

    monkeypatch.setattr(settings, "companion_database_url", "")
    monkeypatch.setattr(settings, "companion_db_host", "")
    assert await build(["--out", str(tmp_path / "out"), "--assets-dir", str(tmp_path)]) == 2
