"""把仓库形象资产清单注册成独立 her（ca_her_pack，source="manual"，draft-first）。

用法（server/ 目录，.env 里有 COMPANION_DATABASE_URL）：
    PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py
    # 给单文件 pack（纸偶 zip / VRM / GLB）现算 model_ref.hash：
    PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py --assets-root <Android 仓库根>
    # 人工验收通过后上架（可多次指定；许可证未过白名单的会被拒绝并说明）：
    PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py --accept simple-demo-avatar-v1

「把所有的 model 都整理成一个个独立的形象」的执行件：清单在 tools/her_registry.py
（取证见 docs/her-inventory-registry-20261128.md §1），本工具只把清单落库。

**draft-first（用户裁决 2026-11-28）**：默认全部 status=draft——注册是登记实体，
上架是验收动作。``--accept <her_id>`` 是验收入口：只有许可证在 own/cc0-1.0 白名单里的
才接受（法律硬闸，验收不能越）；renderer 还没进 release 渲染词表 / pack hash 还缺的，
报告里列出 blockers 供协调排期，但不自动上架。

与 seed_her_packs.py（卡播种）的分工：那张脚本从 persona 卡的 model_ref 派生 her +
默认绑定；本脚本登记**模型资产实体**，不建绑定——换绑是协调动作（换形象不换人格）。
两张脚本写同一张 ca_her_pack，her_id 命名空间不同，互不覆盖。

二进制不入库：hash 现算自 --assets-root，缺文件（dev cache / 引进候选）就是预期路径。
"""

import argparse
import asyncio
import sys
from pathlib import Path

from companion.worker import load_env

load_env()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets-root", type=Path, default=None,
                    help="客户端资产仓库（Android）根目录；给了才对单文件 pack 现算 sha256")
    ap.add_argument("--accept", action="append", default=[], metavar="HER_ID",
                    help="人工验收通过、本次上架 published 的 her_id（可重复；许可证硬闸不越）")
    return ap.parse_args(argv)


async def seed(assets_root: Path | None = None, accept: tuple[str, ...] = ()) -> int:
    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.service.roles.hers import SqlHerPackStore
    from tools.her_registry import ENTRIES, seed_repo_hers

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL（或 COMPANION_MYSQL_URL）", file=sys.stderr)
        return 2
    if assets_root is not None and not assets_root.is_dir():
        print(f"--assets-root 不是目录：{assets_root}", file=sys.stderr)
        return 2

    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        reports = await seed_repo_hers(SqlHerPackStore(engine), ENTRIES,
                                       assets_root, frozenset(accept))
    finally:
        await engine.dispose()

    published = [r for r in reports if r["status"] == "published"]
    for r in reports:
        mark = "OK   " if r["status"] == "published" else "DRAFT"
        extra = ""
        if r["note"]:
            extra = f"  [{r['note']}]"
        elif r["blockers"]:
            extra = "  <- " + "; ".join(r["blockers"])
        print(f"{mark} {r['her_id']:44} v{r['pack_version']}{extra}")
    print(f"registered {len(reports)} her(s): {len(published)} published, "
          f"{len(reports) - len(published)} draft")
    refused = [r for r in reports if r["note"].startswith("accept refused")]
    if refused:
        print("验收被许可证硬闸拒绝: " + ", ".join(r["her_id"] for r in refused),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(seed(args.assets_root, tuple(args.accept))))
