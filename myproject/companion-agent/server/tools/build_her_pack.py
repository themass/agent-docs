"""Hermes M0「数据面演练」：现成资产 → 可安装 her 包，一条链走通到底。

设计出处：docs/hermes-her-production-design-20261128.md §7-M0。意义不是自动化产线，
而是把「产线产物契约 ↔ 端上安装」之间所有未验证假设当场证伪或证实：

    build_asset_pack → validate_asset_pack（G-A 门）→ upsert(source="manual")
        → bind → HerCatalog.invalidate

G-A 门是**服务端版镜像**（设计文档 N7 / T-10）：逐条对应端上
`CharacterAssetPack.kt`（Android 仓库 weifu-refactor 线，commit 5c951543）里
`CharacterAssetPolicy` 的每个拒点——现成的 `validate_payload` 只做结构校验，
挡不住 `files>200`、hash 非 hex、`entry_point` 不在 files 这类「端上必拒」的包。
契约字段清单（manifest 六键 / 引擎枚举 / model_ref 四键）钉在
tests/test_build_her_pack.py 的快照断言里，端上契约变了测试先红。

用法（server/ 目录）：
    # 演练（sqlite 文件库，空库自动建表；不碰生产）
    COMPANION_DATABASE_URL=sqlite+aiosqlite:///drill.db \
      PYTHONPATH=src .venv/bin/python tools/build_her_pack.py \
      --source-zip /path/to/demo-avatar-v1.zip --out build/hers
    # 生产（104，协调会话执行；.env 里有 COMPANION_DATABASE_URL）
    PYTHONPATH=src .venv/bin/python tools/build_her_pack.py \
      --source-zip demo-avatar-v1.zip --out /tmp/her-packs \
      --cdn-base "https://<CDN落点>"

幂等：内容没变不写、不顶 pack_version（规则同 seed_her_packs.py）；产物 zip 每次
重建字节相同（同输入+版本 → 同 sha256，镜像 T-11 的确定性语义）。
N10：asset 名 = pack_id；her_id = <renderer>-<asset>，三处不漂移。
N12：M0 用 source="manual"——hermes 产线还没上线，别伪造来源。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from companion.worker import load_env

load_env()

# ---- 端上契约快照（权威来源：CharacterAssetPack.kt，5c951543） -------------------

# CharacterAssetManifest.parse 读且只读这六个键；多一个浪费，少一个端上 parse 崩。
ASSET_MANIFEST_FIELDS = frozenset(
    {"schema_version", "pack_id", "version", "engine", "entry_point", "files"})

# CharacterEngineType 枚举。**无 VRM**（F-ENGINE-ENUM / 待决 Q2）：端上第二刀扩枚举
# 之前，产线对 VRM 包停在 candidate。
ENGINE_TYPES = ("LAYERED", "LIVE2D", "RIVE", "DUIX", "TAO")

# payload.model_ref 收敛形态（persona/her 分层 §3：{asset, version, hash}）+
# download_url（端上既有下载口径，AvatarSync.kt 读 "download_url"；URL 落点归
# 协调会话的 CDN 决策，字段名归契约）。
MODEL_REF_FIELDS = frozenset({"asset", "version", "hash", "download_url"})

# CharacterAssetPolicy 的正则，逐字符镜像（Kotlin Regex.matches == Python fullmatch）。
_PACK_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_DIGEST = re.compile(r"[0-9a-fA-F]{64}")
_COMPONENT = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}")
_MAX_FILES = 200
_MAX_BYTES = 100 * 1024 * 1024          # MAX_BYTES（端上安装硬顶）
_MAX_PATH = 512


class AssetPackError(ValueError):
    """产物不符合端上契约（G-A 门拒绝；不落库、不出包）。"""


def validate_asset_pack(manifest: dict[str, Any]) -> list[str]:
    """T-10 的 M0 形态：镜像 CharacterAssetPolicy 的每个拒点，返回逐条 violation。

    空列表 = 端上 `CharacterAssetPackStore.install` 在「manifest 合法」这一关上
    必然通过（文件字节与 hash 的一致性由 build 保证、安装时端上复核）。
    """
    violations: list[str] = []
    if manifest.get("schema_version") != 1:
        violations.append("schema_version must be 1")
    pack_id = manifest.get("pack_id")
    if not isinstance(pack_id, str) or not _PACK_ID.fullmatch(pack_id):
        violations.append("pack_id must match [a-z0-9][a-z0-9_-]{0,63}")
    version = manifest.get("version")
    if not isinstance(version, int) or version <= 0:
        violations.append("version must be > 0")
    engine = manifest.get("engine")
    if engine not in ENGINE_TYPES:
        violations.append(f"engine must be one of {list(ENGINE_TYPES)}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        violations.append("files must be a non-empty mapping")
        return violations
    if len(files) > _MAX_FILES:
        violations.append(f"files must have at most {_MAX_FILES} entries")
    if manifest.get("entry_point") not in files:
        violations.append("entry_point must be one of files")
    for path, sha in files.items():
        if not isinstance(path, str) or len(path) > _MAX_PATH:
            violations.append(f"path too long or not a string: {path!r}")
            continue
        for component in path.split("/"):
            if component in (".", "..") or not _COMPONENT.fullmatch(component):
                violations.append(f"unsafe path component: {path!r}")
                break
        if not isinstance(sha, str) or not _DIGEST.fullmatch(sha):
            violations.append(f"file hash must be 64 hex chars: {path!r}")
    return violations


def build_asset_pack(*, files: dict[str, bytes], pack_id: str, version: int,
                     renderer: str, entry_point: str) -> tuple[dict[str, Any], bytes]:
    """T-11 的 M0 形态：文件树 → (端上契约 manifest, zip 字节)。

    确定性：同一输入 + 版本 → 字节相同（zip 内条目按名字排序、时间戳固定），
    所以 model_ref.hash 是对账信号而不是每次重算的随机数。文件级 sha256 在这里
    一次算好写进 manifest——端上安装时逐文件复核的就是这些值。
    """
    # ca_her_pack.renderer 列按现网口径小写（live2d/simple）；端上引擎枚举大写。
    engine = renderer.strip().upper()
    if engine not in ENGINE_TYPES:
        raise AssetPackError(f"renderer {renderer!r} is not a client engine "
                             f"(client enum: {list(ENGINE_TYPES)})")
    if entry_point not in files:
        raise AssetPackError(f"entry_point {entry_point!r} is not in the file tree")
    total = 0
    digests: dict[str, str] = {}
    for path, blob in files.items():
        bad = validate_asset_pack({"schema_version": 1, "pack_id": pack_id,
                                   "version": version, "engine": engine,
                                   "entry_point": entry_point, "files": {path: "ab" * 32}})
        path_problems = [v for v in bad if v.startswith("unsafe path")]
        if path_problems:
            raise AssetPackError(path_problems[0])
        total += len(blob)
        digests[path] = hashlib.sha256(blob).hexdigest()
    if total > _MAX_BYTES:
        raise AssetPackError(f"pack is {total} bytes, over the client limit {_MAX_BYTES}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "pack_id": pack_id,
        "version": version,
        "engine": engine,
        "entry_point": entry_point,
        "files": {path: digests[path] for path in sorted(digests)},
    }
    if (violations := validate_asset_pack(manifest)):
        raise AssetPackError("pack failed the contract gate: " + "; ".join(violations))

    # pack-manifest.json 在包里（工具/人查验用）但不在 files 清单——端上安装只按
    # files 落文件，外契约 manifest 由 /v1/hers 详情链供给。固定时间戳保证确定性。
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                   indent=2).encode()
        zf.writestr(zipfile.ZipInfo("pack-manifest.json", date_time=(1980, 1, 1, 0, 0, 0)),
                    manifest_json)
        for path in sorted(files):
            zf.writestr(zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0)), files[path])
    return manifest, buffer.getvalue()


def build_her_payload(*, name: str, tagline: str, pack_id: str, version: int,
                      pack_sha256: str, cdn_base: str) -> dict[str, Any]:
    """T-12 的 M0 形态：payload 按 persona/her 分层 §3 的 model_ref 收敛形态装配。

    download_url 是占位参数（--cdn-base）：字段名与结构按端上契约写死
    （MODEL_REF_FIELDS），落点归协调会话的 CDN 决策。
    """
    url = f"{cdn_base.rstrip('/')}/{pack_id}/v{version}.zip" if cdn_base else ""
    return {
        "name": name,
        "tagline": tagline,
        "model_ref": {"asset": pack_id, "version": version,
                      "hash": pack_sha256, "download_url": url},
    }


async def deploy_pack(store, *, role_id: str, renderer: str, pack_id: str,
                      version: int, name: str, tagline: str,
                      files: dict[str, bytes], entry_point: str,
                      cdn_base: str, out_dir: Path):
    """完整数据面链：build → G-A 门 → upsert(manual) → bind → invalidate。

    G-A 门不过就抛 AssetPackError——库里不落任何痕迹（写入口严进）。
    """
    from companion.api.http.routers.hers import HerCatalog

    manifest, zip_bytes = build_asset_pack(files=files, pack_id=pack_id,
                                           version=version, renderer=renderer,
                                           entry_point=entry_point)
    payload = build_her_payload(name=name, tagline=tagline, pack_id=pack_id,
                                version=version,
                                pack_sha256=hashlib.sha256(zip_bytes).hexdigest(),
                                cdn_base=cdn_base)
    her_id = f"{renderer}-{pack_id}"            # D-HID；asset == pack_id（N10）
    rec = await store.upsert(her_id=her_id, renderer=renderer, payload=payload,
                             status="published", source="manual")
    await store.bind(role_id=role_id, her_id=her_id, is_default=True)
    HerCatalog(store).invalidate()              # 进程级缓存失效（本进程口径）

    out_dir.mkdir(parents=True, exist_ok=True)
    pack_path = out_dir / f"{pack_id}-v{version}.zip"
    pack_path.write_bytes(zip_bytes)
    return rec


def _read_files(assets_dir: Path | None, source_zip: Path | None) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if source_zip is not None:
        with zipfile.ZipFile(source_zip) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                files[info.filename] = zf.read(info)
    if assets_dir is not None:
        for path in sorted(assets_dir.rglob("*")):
            if path.is_file():
                files[str(path.relative_to(assets_dir))] = path.read_bytes()
    return files


async def build(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets-dir", type=Path,
                        help="目录树：每个文件的相对路径就是包内路径")
    parser.add_argument("--source-zip", type=Path,
                        help="现成 zip（如端上内置的 demo-avatar-v1.zip），文件原样进包")
    parser.add_argument("--out", type=Path, required=True, help="产物 zip 落点目录")
    parser.add_argument("--pack-id", default=None,
                        help="默认取 source-zip 文件名去掉 .zip（N10：asset = pack_id）")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--renderer", default="layered",
                        help=f"端上引擎（{list(ENGINE_TYPES)} 的小写）")
    parser.add_argument("--entry-point", default="manifest.json")
    parser.add_argument("--role-id", default="linche", help="默认绑定的角色")
    parser.add_argument("--name", default=None)
    parser.add_argument("--tagline", default="Hermes M0 数据面演练包")
    parser.add_argument("--cdn-base", default="",
                        help="download_url 前缀占位（生产 CDN 落点归协调会话）")
    args = parser.parse_args(argv)

    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.service.roles.hers import SqlHerPackStore

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL（或 COMPANION_MYSQL_URL）", file=sys.stderr)
        return 2
    if not (args.assets_dir or args.source_zip):
        print("需要 --assets-dir 或 --source-zip 之一", file=sys.stderr)
        return 2
    files = _read_files(args.assets_dir, args.source_zip)
    if not files:
        print("资产为空：--assets-dir 没有文件 / --source-zip 是空包", file=sys.stderr)
        return 2

    pack_id = args.pack_id or (
        args.source_zip.stem if args.source_zip else args.assets_dir.name)
    name = args.name or pack_id

    # 一次性工具用最小档连接池；演练库（sqlite 文件）空表时先建表——生产库走
    # alembic（head ≥0005），这里不跑迁移也不该跑。
    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        if settings.database_url.startswith("sqlite"):
            import companion.agent.memory.sql  # noqa: F401 —— 注册 ca_memory_item
            from companion.db.schema import metadata
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
        try:
            rec = await deploy_pack(
                SqlHerPackStore(engine), role_id=args.role_id, renderer=args.renderer,
                pack_id=pack_id, version=args.version, name=name,
                tagline=args.tagline, files=files, entry_point=args.entry_point,
                cdn_base=args.cdn_base, out_dir=args.out)
        except AssetPackError as exc:
            print(f"G-A 契约门拒绝：{exc}", file=sys.stderr)
            return 1
    finally:
        await engine.dispose()

    print(f"her pack: {rec.her_id}  pack_version={rec.pack_version}  "
          f"status={rec.status} source={rec.source}")
    print(f"pack: {args.out / f'{pack_id}-v{args.version}.zip'}  "
          f"({args.renderer.upper()}, {len(files)} files, entry={args.entry_point})")
    print(f"model_ref: {json.dumps(rec.payload['model_ref'], ensure_ascii=False)}")
    print(f"bound: {args.role_id} -> {rec.her_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(build()))
