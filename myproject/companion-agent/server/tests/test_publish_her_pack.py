"""her 发布链（tools/publish_her_pack.py）+ /v1/hers 签名/persona join。

设计出处：docs/her-tos-delivery-design-20261128.md。对象存储用 InMemoryObjectStore
（memory:// 占位签名）——这里钉的是机制：**key 进 payload、URL 读时现签、永不落库**，
TOS 真桶由演练对账（见 run log），不在单测里连网。

钉死的行为：
- draft-first（用户裁决 2026-11-28）：发布默认 draft 登记；--accept 才 published，
  且可发布许可证硬闸（own/cc0-1.0）不能豁免。
- renderer 词表进、端上引擎枚举出：simple（词表）→ LAYERED（manifest engine）。
- 库里 payload 的 download_url 留空占位；签名 URL 只出现在响应里（带 url_expires_in）。
- persona 半经 ca_character_her join 角色卡；没绑定/读不出卡 → null，不 404。
"""

from __future__ import annotations

import json

import pytest

from companion.api.http.routers.hers import HerCatalog
from companion.service.roles.hers import SqlHerPackStore
from companion.service.roles.packs import DbCharacterSource, SqlCharacterPackStore
from companion.service.uploads.memory_storage import InMemoryObjectStore
from tools.publish_her_pack import PublishError, pack_object_key, publish


def _files() -> dict[str, bytes]:
    inner = {"id": "kira-layers-v1", "canvas": {"w": 512, "h": 768},
             "layers": [{"id": "body", "path": "layers/body.png", "z": 0}]}
    return {"manifest.json": json.dumps(inner).encode(),
            "layers/body.png": b"\x89PNG\r\n\x1a\n fake body layer"}


async def _publish(store, objects, **over):
    opts = dict(store=store, objects=objects, tos_key_prefix="companion-qa/",
                files=_files(), pack_id="kira-songstress", version=1,
                renderer="simple", entry_point="manifest.json",
                name="绮拉", tagline="会写词的电子歌姬", role_id=None,
                thumbnail=None, portrait=None, source="hermes",
                accept=False, license_id="")
    opts.update(over)
    return await publish(**opts)


# ---- 发布链：先对象后库，draft-first，许可证硬闸 ----------------------------------

async def test_publish_uploads_object_then_registers_draft(sqlite_engine):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    receipt = await _publish(store, objects)
    key = pack_object_key("companion-qa/", "kira-songstress", 1)
    assert await objects.head_size(key=key) == receipt["size_bytes"]
    assert receipt["her_id"] == "simple-kira-songstress"
    assert receipt["status"] == "draft"                 # 登记 ≠ 上架
    rec = await store.load("simple-kira-songstress")
    assert rec.payload["object_key"] == key
    assert rec.payload["model_ref"]["download_url"] == ""   # 签名 URL 永不落库


async def test_accept_requires_publishable_license(sqlite_engine):
    with pytest.raises(PublishError, match="license"):
        await _publish(SqlHerPackStore(sqlite_engine), InMemoryObjectStore(),
                       accept=True, license_id="live2d-free-collection")


async def test_accept_with_own_license_publishes(sqlite_engine):
    receipt = await _publish(SqlHerPackStore(sqlite_engine), InMemoryObjectStore(),
                             accept=True, license_id="own")
    assert receipt["status"] == "published"


async def test_renderer_outside_vocab_rejected(sqlite_engine):
    with pytest.raises(PublishError, match="renderer"):
        await _publish(SqlHerPackStore(sqlite_engine), InMemoryObjectStore(),
                       renderer="hologram")


async def test_simple_word_maps_to_layered_engine_in_pack(sqlite_engine):
    # 词表裁决（simple）与端上枚举（LAYERED）在映射表处衔接，两边都不漂移。
    receipt = await _publish(SqlHerPackStore(sqlite_engine), InMemoryObjectStore())
    assert receipt["engine"] == "LAYERED"


async def test_publish_rerun_is_idempotent(sqlite_engine):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    first = await _publish(store, objects)
    again = await _publish(store, objects)
    assert first["pack_version"] == again["pack_version"] == 1


async def test_thumbnail_and_portrait_upload_and_key_registered(sqlite_engine, tmp_path):
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG\r\n\x1a\n thumb-bytes")
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    await _publish(store, objects, thumbnail=thumb)
    rec = await store.load("simple-kira-songstress")
    key = rec.payload["thumbnail_key"]
    assert key == "companion-qa/hers/kira-songstress/v1/thumbnail.png"
    assert await objects.head_size(key=key) == thumb.stat().st_size


# ---- /v1/hers 读路径：现签 + persona join -----------------------------------------

_CARD = {"spec": "chara_card_v2", "spec_version": "2.0", "data": {
    "name": "小笺", "description": "安静的手账师", "personality": "句子短但准",
    "first_mes": "", "mes_example": "",
    "model_ref": {"renderer": "simple", "asset": "kira-songstress"}}}


def _catalog(store, objects, characters=None):
    return HerCatalog(store, objects=objects, characters=characters)


async def test_detail_signs_download_thumbnail_and_joins_persona(sqlite_engine):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    await _publish(store, objects, accept=True, license_id="own",
                   role_id="mo-handjournal")
    await SqlCharacterPackStore(sqlite_engine).upsert(
        role_id="mo-handjournal", payload=_CARD, renderer="simple",
        pack_asset="kira-songstress", source="manual")

    catalog = _catalog(store, objects,
                       characters=DbCharacterSource(SqlCharacterPackStore(sqlite_engine)))
    detail = (await catalog.get("simple-kira-songstress")).to_json()
    assert detail["model_ref"]["download_url"].startswith("memory://")
    assert detail["model_ref"]["url_expires_in"] == 3600
    assert detail["model_ref"]["size_bytes"] > 0
    assert detail["portrait_url"] == ""              # 没传 portrait 就是空，不是缺键
    assert detail["persona"] == {"role_id": "mo-handjournal", "name": "小笺",
                                 "description": "安静的手账师", "personality": "句子短但准"}


async def test_list_signs_thumbnail_url(sqlite_engine, tmp_path):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG\r\n\x1a\n thumb")
    await _publish(store, objects, thumbnail=thumb, accept=True, license_id="own")
    items, _ = await _catalog(store, objects).list()
    assert items[0].thumbnail_url.startswith("memory://")
    assert items[0].url_expires_in == 3600


async def test_draft_row_is_hidden_from_c_end_list(sqlite_engine):
    # draft-first 的闸在列表：登记后未验收 → C 端目录看不见（详情仍可直达）。
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    await _publish(store, objects)                      # 默认 draft
    items, total = await _catalog(store, objects).list()
    assert items == [] and total == 0
    detail = (await _catalog(store, objects).get("simple-kira-songstress")).to_json()
    assert detail["status"] == "draft"                  # 验收/深链路径不断


async def test_no_object_storage_gives_empty_urls_not_error(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await _publish(store, InMemoryObjectStore(), accept=True, license_id="own")
    detail = (await _catalog(store, objects=None).get("simple-kira-songstress")).to_json()
    assert detail["model_ref"]["download_url"] == ""   # 库里占位原样出去
    assert detail["thumbnail_url"] == ""
    items, _ = await _catalog(store, objects=None).list()
    assert items[0].thumbnail_url == ""


async def test_unbound_her_persona_is_null_not_404(sqlite_engine):
    store = SqlHerPackStore(sqlite_engine)
    await _publish(store, InMemoryObjectStore())
    detail = (await _catalog(store, InMemoryObjectStore()).get(
        "simple-kira-songstress")).to_json()
    assert detail["persona"] is None


async def test_binding_without_card_gives_null_persona(sqlite_engine):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    await _publish(store, objects, role_id="ghost-role")   # 绑了但角色没播种
    detail = (await _catalog(store, objects,
                             characters=DbCharacterSource(
                                 SqlCharacterPackStore(sqlite_engine)))
              .get("simple-kira-songstress")).to_json()
    assert detail["persona"] is None


async def test_effects_catalog_items_get_signed_urls(sqlite_engine):
    store, objects = SqlHerPackStore(sqlite_engine), InMemoryObjectStore()
    receipt = await _publish(store, objects)
    rec = await store.load("simple-kira-songstress")
    await store.upsert(her_id=rec.her_id, renderer=rec.renderer, status="published",
                       source="hermes",
                       payload={**rec.payload, "effects": [
                           {"id": "fx_wave", "anchor": "FULL", "key": "companion-qa/effects/fx_wave/v1.json"},
                           {"id": "fx_legacy_nokey"}]})
    await objects.put(key="companion-qa/effects/fx_wave/v1.json",
                      data=b"{}", content_type="application/json")
    detail = (await _catalog(store, objects).get(rec.her_id)).to_json()
    assert detail["effects"][0]["url"].startswith("memory://")
    assert "url" not in detail["effects"][1]          # 纯策略目录项不加 URL 键
