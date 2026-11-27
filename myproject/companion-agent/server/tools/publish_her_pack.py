"""her 包发布：产物上 TOS + 注册表写入，一条链走完（T-18 publish_release 第一刀）。

设计出处：docs/her-tos-delivery-design-20261128.md（TOS 目录结构、发布顺序、draft-first）。
它补上 M0 演练明确留白的那一段：build_her_pack.py 把 zip 写在本机 --out，
本工具把同样的确定性产物 **传到 TOS**，并把对象 key 记进 payload——
此后 /v1/hers 详情才能现签 download_url（avatars 线同款，service/avatar/catalog.py）。

顺序固定，不留半写（镜像 AvatarCatalog.upload 的回滚语义）：

    build_asset_pack（G-A 门） → put zip → head 复核 → put thumbnail/portrait
        → upsert ca_her_pack（--accept 才 published） → bind → invalidate → receipt

draft-first（用户裁决 2026-11-28，tools/her_registry.py）：默认写 ``draft``——
上传与注册是登记；上架是验收动作，要 ``--accept`` + 可发布许可证
（own / cc0-1.0，法律硬闸不豁免）。

用法（server/ 目录；TOS_* 与 COMPANION_DATABASE_URL 来自 .env）：
    PYTHONPATH=src .venv/bin/python tools/publish_her_pack.py \
        --assets-dir /tmp/stage --pack-id kira-songstress --renderer simple \
        --name 绮拉 --tagline 会写词的电子歌姬 --thumbnail portrait.png \
        --source hermes --accept --license own [--role-id kira-songstress]

幂等：同输入重跑 → 对象同字节覆盖、库不顶 pack_version（SqlHerPackStore 规则）。
对象 key 规则（设计 §2）：
    {TOS_KEY_PREFIX}hers/<pack_id>/v<N>.zip
    {TOS_KEY_PREFIX}hers/<pack_id>/v<N>/thumbnail.jpg   （portrait 同目录）
旧版本对象永不覆盖；下架走 status→retired，不删对象。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

from companion.worker import load_env

load_env()

from tools.build_her_pack import (  # noqa: E402  （load_env 必须先跑）
    AssetPackError,
    _read_files,
    build_asset_pack,
    build_her_payload,
)
from tools.her_registry import (  # noqa: E402
    LICENSE_VOCAB,
    PUBLISHABLE_LICENSES,
    RENDERER_VOCAB,
)

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp"}


class PublishError(RuntimeError):
    pass


def pack_object_key(prefix: str, pack_id: str, version: int) -> str:
    return f"{prefix}hers/{pack_id}/v{version}.zip"


def image_object_key(prefix: str, pack_id: str, version: int, name: str) -> str:
    return f"{prefix}hers/{pack_id}/v{version}/{name}"


async def publish(*, store, objects, tos_key_prefix: str, files: dict[str, bytes],
                  pack_id: str, version: int, renderer: str, entry_point: str,
                  name: str, tagline: str, role_id: str | None,
                  thumbnail: Path | None, portrait: Path | None,
                  source: str, accept: bool, license_id: str) -> dict[str, Any]:
    """完整发布链。返回 receipt（打印与 run log 都用它）。"""
    if renderer not in RENDERER_VOCAB:
        raise PublishError(f"renderer {renderer!r} 不在词表 {sorted(RENDERER_VOCAB)}")
    if accept and license_id not in PUBLISHABLE_LICENSES:
        raise PublishError(
            f"accept refused: license {license_id!r} 过不了可发布硬闸 "
            f"（可发布={sorted(PUBLISHABLE_LICENSES)}）；登记可以，上架不行")
    if license_id and license_id not in LICENSE_VOCAB:
        raise PublishError(f"unknown license id: {license_id!r}")

    manifest, zip_bytes = build_asset_pack(files=files, pack_id=pack_id, version=version,
                                           renderer=renderer, entry_point=entry_point)
    digest = hashlib.sha256(zip_bytes).hexdigest()

    key = pack_object_key(tos_key_prefix, pack_id, version)
    await objects.put(key=key, data=zip_bytes, content_type="application/zip")
    head = await objects.head_size(key=key)
    if head != len(zip_bytes):
        raise PublishError(f"对象复核失败：head={head} != {len(zip_bytes)}")

    payload = build_her_payload(name=name, tagline=tagline, pack_id=pack_id,
                                version=version, pack_sha256=digest, cdn_base="")
    # 对象 key 进 payload（不加列不动迁移，head 仍 0005）；download_url 留空占位，
    # 真 URL 只在响应里现签——签名 URL 是 bearer secret，永不落库。
    payload["object_key"] = key
    payload["size_bytes"] = head

    for path, slot in ((thumbnail, "thumbnail"), (portrait, "portrait")):
        if path is None:
            continue
        ext = path.suffix.lower()
        if ext not in IMAGE_TYPES:
            raise PublishError(f"{slot} 只收 png/jpg/webp，收到 {ext!r}")
        blob = path.read_bytes()
        image_key = image_object_key(tos_key_prefix, pack_id, version, f"{slot}{ext}")
        await objects.put(key=image_key, data=blob, content_type=IMAGE_TYPES[ext])
        payload[f"{slot}_key"] = image_key

    from companion.api.http.routers.hers import HerCatalog

    status = "published" if accept else "draft"
    rec = await store.upsert(her_id=f"{renderer}-{pack_id}", renderer=renderer,
                             payload=payload, status=status, source=source)
    if role_id:
        await store.bind(role_id=role_id, her_id=rec.her_id, is_default=True)
    HerCatalog(store).invalidate()
    return {"her_id": rec.her_id, "pack_version": rec.pack_version, "status": rec.status,
            "source": rec.source, "object_key": key, "zip_sha256": digest,
            "size_bytes": head, "files": len(files), "engine": manifest["engine"]}


async def publish_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="her 包发布到 TOS + 注册表（draft-first）")
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--renderer", required=True,
                        help=f"renderer 词表：{sorted(RENDERER_VOCAB)}")
    parser.add_argument("--entry-point", default="manifest.json")
    parser.add_argument("--name", default=None)
    parser.add_argument("--tagline", default="")
    parser.add_argument("--role-id", default=None, help="给了就绑默认")
    parser.add_argument("--thumbnail", type=Path, default=None)
    parser.add_argument("--portrait", type=Path, default=None)
    parser.add_argument("--source", required=True, choices=["hermes", "manual", "card"])
    parser.add_argument("--accept", action="store_true",
                        help="验收上架（status=published）；不填则 draft 登记")
    parser.add_argument("--license", default="",
                        help=f"--accept 必填；可发布={sorted(PUBLISHABLE_LICENSES)}")
    args = parser.parse_args(argv)

    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.service.roles.hers import SqlHerPackStore
    from companion.service.uploads.tos import TosObjectStore

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL", file=sys.stderr)
        return 2
    if not settings.tos_endpoint:
        print("缺少 TOS_ENDPOINT——发布必须有对象存储（演练用 build_her_pack.py）",
              file=sys.stderr)
        return 2
    files = _read_files(args.assets_dir, None)
    if not files:
        print(f"资产为空：{args.assets_dir}", file=sys.stderr)
        return 2

    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        try:
            receipt = await publish(
                store=SqlHerPackStore(engine),
                objects=TosObjectStore(endpoint=settings.tos_endpoint,
                                       bucket=settings.tos_bucket,
                                       access_key=settings.tos_access_key,
                                       secret_key=settings.tos_secret_key,
                                       region=settings.tos_region),
                tos_key_prefix=settings.tos_key_prefix or "",
                files=files, pack_id=args.pack_id, version=args.version,
                renderer=args.renderer, entry_point=args.entry_point,
                name=args.name or args.pack_id, tagline=args.tagline,
                role_id=args.role_id, thumbnail=args.thumbnail, portrait=args.portrait,
                source=args.source, accept=args.accept, license_id=args.license)
        except (AssetPackError, PublishError) as exc:
            print(f"发布失败：{exc}", file=sys.stderr)
            return 1
    finally:
        await engine.dispose()

    for k, v in receipt.items():
        print(f"{k}: {v}")
    print("✅ published")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(publish_main()))
