"""把仓库形象资产清单注册成独立 her（ca_her_pack，source="manual"）。

用法（server/ 目录，.env 里有 COMPANION_DATABASE_URL）：
    PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py
    # 给单文件 pack（纸偶 zip / VRM / GLB）现算 model_ref.hash：
    PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py --assets-root <Android 仓库根>

「把所有的 model 都整理成一个个独立的形象」的执行件：清单在 tools/her_registry.py
（取证见 docs/her-inventory-registry-20261128.md §1），本工具只把清单落库。

与 seed_her_packs.py（卡播种）的分工：那张脚本从 persona 卡的 model_ref 派生 her +
默认绑定；本脚本登记**模型资产实体**，不建绑定——换绑是协调动作（换形象不换人格）。
两张脚本写同一张 ca_her_pack，her_id 命名空间不同，互不覆盖。

状态由三道闸决定（her_registry.decide_status：许可证 ∧ renderer ∧ pack hash）：
闸门没过就是 draft，这是清单的语义，不是失败。二进制不入库——hash 现算自
--assets-root，缺文件（dev cache / 引进候选）就是预期内的 draft。
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
    ap.add_argument("--status", choices=("all", "published", "draft"), default="all",
                    help="只注册某一类（调试/放量用：词表拍板后 --status published 只推可上架行）")
    return ap.parse_args(argv)


async def seed(assets_root: Path | None = None, status: str = "all") -> int:
    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.service.roles.hers import SqlHerPackStore
    from tools.her_registry import (
        ENTRIES, PRODUCTION_RENDERERS, PUBLISHABLE_LICENSES, seed_repo_hers)

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL（或 COMPANION_MYSQL_URL）", file=sys.stderr)
        return 2
    if assets_root is not None and not assets_root.is_dir():
        print(f"--assets-root 不是目录：{assets_root}", file=sys.stderr)
        return 2

    # 静态两道闸先筛（许可证 / renderer）——pack hash 要读文件，不在这里预先算。
    entries = ENTRIES if status == "all" else tuple(
        e for e in ENTRIES
        if (status == "published") == (e.license_id in PUBLISHABLE_LICENSES
                                       and e.renderer in PRODUCTION_RENDERERS))
    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        reports = await seed_repo_hers(SqlHerPackStore(engine), entries, assets_root)
    finally:
        await engine.dispose()
    if not reports:
        print("清单为空或全部被 --status 过滤", file=sys.stderr)
        return 1
    published = [r for r in reports if r["status"] == "published"]
    for r in reports:
        mark = "OK " if r["status"] == "published" else "DRAFT"
        note = "" if r["status"] == "published" else f"  <- {r['reason']}"
        print(f"{mark} {r['her_id']:44} v{r['pack_version']}{note}")
    print(f"registered {len(reports)} her(s): {len(published)} published, "
          f"{len(reports) - len(published)} draft")
    if not published:
        # 一条都上不了架通常是 assets-root 忘了给——报非零让部署看见。
        print("没有任何 her 达到 published（license/renderer/hash 三道闸）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(seed(args.assets_root, args.status)))
