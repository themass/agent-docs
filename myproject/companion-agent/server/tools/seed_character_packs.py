"""把随包发布的角色卡（agent/characters/*.v2.json）播种进 ca_character_pack。

用法（server/ 目录，.env 里有 COMPANION_MYSQL_URL / COMPANION_DATABASE_URL）：
    PYTHONPATH=src .venv/bin/python tools/seed_character_packs.py

幂等：内容没变不写、不顶 pack_version；变了 +1。部署在迁移之后跑它，
运行时（角色解析、目录、音色）就以库里的封装为准，文件只作未播种环境的兜底。
坏文件跳过并报告——一张文件坏了不该把全部封装挡在库外。
"""

import asyncio
import sys

from companion.worker import load_env

load_env()


async def seed() -> int:
    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.paths import CHARACTERS_DIR
    from companion.service.roles.packs import seed_from_files, SqlCharacterPackStore

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL（或 COMPANION_MYSQL_URL）", file=sys.stderr)
        return 2
    # 一次性工具用最小档连接池，跑完释放。
    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        seeded = await seed_from_files(SqlCharacterPackStore(engine), CHARACTERS_DIR)
    finally:
        await engine.dispose()
    if not seeded:
        print(f"没有播种任何角色：{CHARACTERS_DIR} 下没有可解析的 *.v2.json", file=sys.stderr)
        return 1
    print(f"seeded {len(seeded)} pack(s): {', '.join(seeded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed()))
