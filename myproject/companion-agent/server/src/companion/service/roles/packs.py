"""角色封装在库里的形态：系统角色包（ca_character_pack）之上的 store 与读取链。

分工（与 ca_role_card 对照）：

- 这张表是**系统角色包**——随包发布的角色卡播种进来，无 owner，一行一个角色：
  完整 V2 卡一份 payload，外加 renderer / pack_asset 两个从卡里 ``model_ref`` 提取的
  **技术判别**列（客户端按它选数字人引擎、按 pack_asset 找形象包）。
- ca_role_card 仍是**用户侧覆盖链**（按 owner 隔离，「这个用户想微调的部分」）。
  解析时系统包在前、用户覆盖最后——两边不互相顶掉（见 service/roles/resolver.py）。

读取链是 ``ChainedCharacterSource``：库优先、文件兜底。两条路径必须在同一进程里共存——
没跑过播种的部署直接把角色页读空是不可接受的；而播种之后，运行时以库为准，
「改了没生效」不再取决于哪台机器的磁盘。

坏行不抛：payload 解析不出来时 ``load`` 给 ``None``、``list_records`` 跳过它——
角色是发布资产，一张坏卡不该让回合、房间或列表页连坐（与文件源同一口径）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.agent.roles.card import CharacterCard, CharacterFormatError, from_v2_json
from companion.db.schema import character_pack

_CARD_SUFFIX = ".v2.json"


def renderer_of(card: Any) -> str:
    """卡上的技术判别（数字人引擎类型）。只认映射里的 ``renderer`` 键。

    ``model_ref`` 在外部卡里可能是个字符串（历史形态，如 "default-chat"）——
    那只是模型路由的标签，不是引擎判别，不能当 renderer 透传给客户端。
    """
    ref = getattr(card, "model_ref", None)
    if isinstance(ref, dict):
        return str(ref.get("renderer") or "").strip()
    return ""


def pack_asset_of(card: Any) -> str:
    ref = getattr(card, "model_ref", None)
    if isinstance(ref, dict):
        return str(ref.get("asset") or "").strip()
    return ""


@dataclass(frozen=True, slots=True)
class PackRecord:
    role_id: str
    payload: dict[str, Any]
    card: CharacterCard
    renderer: str
    pack_asset: str
    pack_version: int
    source: str


class SqlCharacterPackStore:
    """ca_character_pack 的 SQL 实现。单语句读写走 autocommit（理由同 SqlCardStore）。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def load(self, role_id: str) -> PackRecord | None:
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(character_pack)
                                      .where(character_pack.c.role_id == role_id))).mappings().first()
        return _record(row) if row is not None else None

    async def list_records(self) -> list[PackRecord]:
        async with self._auto.connect() as conn:
            result = await conn.execute(select(character_pack).order_by(character_pack.c.role_id))
            rows = result.mappings().all()
        return [rec for row in rows if (rec := _record(row)) is not None]

    async def upsert(self, *, role_id: str, payload: dict[str, Any], renderer: str,
                     pack_asset: str, source: str) -> PackRecord:
        """写入一个系统包；内容变了 pack_version +1，没变就不写。

        部署会反复跑播种，幂等是前提：否则每次部署都凭空顶版本号，
        对账时看不出「这份封装真的改过」。payload 解析不出卡时当场拒绝——
        写入口严进，读路径才宽出（坏行多半来自库内手改或半截写入）。
        """
        card = _parse(payload, role_id)
        if card is None:
            raise ValueError(f"payload is not a parseable character card: {role_id}")
        now = datetime.now(UTC)
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(character_pack)
                                      .where(character_pack.c.role_id == role_id))).mappings().first()
            if row is None:
                await conn.execute(insert(character_pack).values(
                    role_id=role_id, payload=payload, renderer=renderer, pack_asset=pack_asset,
                    pack_version=1, source=source, created_at=now, updated_at=now))
                version = 1
            else:
                unchanged = (dict(row["payload"] or {}) == payload
                             and row["renderer"] == renderer and row["pack_asset"] == pack_asset)
                version = row["pack_version"]
                if not unchanged:
                    version += 1
                    await conn.execute(update(character_pack)
                                       .where(character_pack.c.role_id == role_id)
                                       .values(payload=payload, renderer=renderer,
                                               pack_asset=pack_asset, pack_version=version,
                                               source=source, updated_at=now))
        card = _parse(payload, role_id)
        assert card is not None
        return PackRecord(role_id, payload, card, renderer, pack_asset, version, source)


def _parse(payload: Any, role_id: str) -> CharacterCard | None:
    if not isinstance(payload, dict):
        return None
    try:
        card = from_v2_json(payload)
    except (CharacterFormatError, ValueError):
        return None
    if not card.id:
        card.id = role_id  # 按行补 id：目录与解析都拿它当 role_id，与文件源同一口径
    return card


def _record(row) -> PackRecord | None:
    payload = dict(row["payload"] or {})
    card = _parse(payload, row["role_id"])
    if card is None:
        return None
    return PackRecord(role_id=row["role_id"], payload=payload, card=card,
                      renderer=row["renderer"] or "", pack_asset=row["pack_asset"] or "",
                      pack_version=row["pack_version"], source=row["source"] or "")


class DbCharacterSource:
    """库里的系统包，按 CharacterSourcePort 的口径（未命中抛 FileNotFoundError）。

    resolver 的「没有这个角色」判据钉的就是这个异常——换实现不能换语义。
    """

    def __init__(self, store: SqlCharacterPackStore) -> None:
        self._store = store

    async def load(self, character_id: str) -> CharacterCard:
        rec = await self._store.load(character_id)
        if rec is None:
            raise FileNotFoundError(f"character not found: {character_id}")
        card = rec.card
        # 判别列补进卡：旧卡没写 model_ref 时，目录与引擎选择仍只认卡这一条路。
        if not card.model_ref and rec.renderer:
            card.model_ref = {"renderer": rec.renderer, "asset": rec.pack_asset}
        return card

    async def cards(self) -> dict[str, CharacterCard]:
        return {rec.role_id: await self.load(rec.role_id) for rec in await self._store.list_records()}


class ChainedCharacterSource:
    """按顺序尝试多个来源：先库、后文件。谁先命中听谁的。

    ``cards()`` 合并全部来源（库里已封装的 + 还没播种的），列表页在迁移期两边都能看见；
    同一个 id 以先出现的来源为准。
    """

    def __init__(self, sources: tuple[Any, ...] | list[Any]) -> None:
        self._sources = tuple(sources)

    async def load(self, character_id: str) -> CharacterCard:
        for source in self._sources:
            try:
                return await source.load(character_id)
            except FileNotFoundError:
                continue
        raise FileNotFoundError(f"character not found: {character_id}")

    async def cards(self) -> dict[str, CharacterCard]:
        merged: dict[str, CharacterCard] = {}
        for source in self._sources:
            loader = getattr(source, "cards", None)
            if loader is None:
                continue
            for role_id, card in (await loader()).items():
                merged.setdefault(role_id, card)
        return merged


async def seed_from_files(store: SqlCharacterPackStore, root: Path) -> list[str]:
    """把 ``agent/characters/*.v2.json`` 播种进库。返回播种成功的角色 id。

    坏文件跳过不拦整批——一条文件坏了就把全部封装挡在库外，比重复部署的麻烦更大。
    renderer / pack_asset 从卡里提取（``model_ref.renderer`` / ``model_ref.asset``），
    提取不到就留空列：没有判别只是「客户端退回默认引擎」，不是错误。
    """
    seeded: list[str] = []
    for path in sorted(root.glob(f"*{_CARD_SUFFIX}")):
        role_id = path.name[: -len(_CARD_SUFFIX)]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            card = from_v2_json(payload)
        except (OSError, CharacterFormatError, ValueError):
            continue
        await store.upsert(role_id=role_id, payload=payload,
                           renderer=renderer_of(card), pack_asset=pack_asset_of(card), source="file")
        seeded.append(role_id)
    return seeded
