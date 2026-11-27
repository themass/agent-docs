"""把角色卡里的 model_ref 播种成 her 包 + 默认绑定（ca_her_pack / ca_character_her）。

用法（server/ 目录，.env 里有 COMPANION_DATABASE_URL）：
    PYTHONPATH=src .venv/bin/python tools/seed_her_packs.py

persona/her 分层第一刀（docs/design/2026-11-28-persona-her-split-architecture.md §3）：
现有角色的呈现信息一直住在卡里的映射形 ``model_ref``——本工具把它转成独立的
呈现实体（her_id = ``<renderer>-<asset>``）并建默认绑定；此后「换形象不换人格」
只改绑定，不动卡。声明跑在 seed_character_packs 之后（读角色链，库里优先）。

幂等：内容没变不写、不顶 pack_version（规则同 seed_character_packs.py）。
卡没有映射形 model_ref 的角色跳过并报告——没有呈现声明不是错误，客户端退回默认引擎。
"""

import asyncio
import sys

from companion.worker import load_env

load_env()


async def seed() -> int:
    from companion.bootstrap.database import make_engine, profile_for
    from companion.config import settings
    from companion.paths import CHARACTERS_DIR
    from companion.agent.roles.files import CharacterSource
    from companion.service.roles.hers import SqlHerPackStore, seed_from_cards
    from companion.service.roles.packs import (
        ChainedCharacterSource, DbCharacterSource, SqlCharacterPackStore)

    if not settings.database_url:
        print("缺少 COMPANION_DATABASE_URL（或 COMPANION_MYSQL_URL）", file=sys.stderr)
        return 2
    # 一次性工具用最小档连接池，跑完释放。
    engine = make_engine(settings.database_url, profile_for("jobs"))
    try:
        source = ChainedCharacterSource(
            (DbCharacterSource(SqlCharacterPackStore(engine)), CharacterSource(CHARACTERS_DIR)))
        cards = await source.cards()
        seeded, skipped = await seed_from_cards(SqlHerPackStore(engine), cards)
    finally:
        await engine.dispose()
    if not seeded:
        print("没有播种任何 her 包：角色链里没有带映射形 model_ref 的卡", file=sys.stderr)
        return 1
    print(f"seeded {len(seeded)} her binding(s): {', '.join(seeded)}")
    if skipped:
        print(f"skipped (no presentation declared): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed()))
