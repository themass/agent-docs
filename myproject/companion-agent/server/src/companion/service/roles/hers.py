"""her 包（呈现实体）在库里的形态：ca_her_pack + ca_character_her 之上的 store。

persona/her 分层的服务端第一刀（docs/design/2026-11-28-persona-her-split-architecture.md §3）：

- ``ca_her_pack`` 是**系统 her 包**——引擎中立的呈现实体注册表，无 owner，一行一个 her。
  renderer 是这一行的属性，不是角色的属性：换形象不连带换人格记录，用户自定义 her
  只能挂在非 Live2D 引擎上（Expandable Application 条款），都由这条结构保证。
- ``ca_character_her`` 是角色 ↔ her 的绑定。默认一对一；多候选是「同一个她可以换形象」
  的扩展位，解析只取 ``is_default``。
- 不做用户 her（``ca_user_her``）：那是 P1-01，本次只落注册表与接口。

payload 服务端不解析细节（model_ref/effects/stickers/voice_ref/thumbnail/touch_zones
都是端上按契约校验的呈现声明），所以「写入口严进」这条只能严在**结构**上：payload
必须是映射、model_ref 若存在必须是映射。这跟 packs.py 严在「必须是可解析的 V2 卡」
是同一思路——坏行不该让列表页连坐，读路径宽出（解析不出就跳过）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import character_her, her_pack

HER_STATUSES = ("draft", "published", "retired")


class HerPayloadError(ValueError):
    """payload 结构不合法（写入口拒绝）。"""


def validate_payload(payload: Any) -> dict[str, Any]:
    """最小的结构校验。细节归端上契约，这里只挡半截写入。"""
    if not isinstance(payload, dict):
        raise HerPayloadError("her payload must be a mapping")
    ref = payload.get("model_ref")
    if ref is not None and not isinstance(ref, dict):
        raise HerPayloadError("model_ref must be a mapping")
    for key in ("effects", "stickers", "touch_zones"):
        value = payload.get(key)
        if value is not None and not isinstance(value, list):
            raise HerPayloadError(f"{key} must be a list")
    return payload


@dataclass(frozen=True, slots=True)
class HerPackRecord:
    her_id: str
    renderer: str
    pack_version: int
    payload: dict[str, Any]
    status: str
    source: str

    @property
    def name(self) -> str:
        return str(self.payload.get("name") or self.her_id)

    @property
    def tagline(self) -> str:
        return str(self.payload.get("tagline") or "")

    @property
    def model_ref(self) -> dict[str, Any]:
        ref = self.payload.get("model_ref")
        return dict(ref) if isinstance(ref, dict) else {}

    @property
    def voice_ref(self) -> dict[str, str] | None:
        """对外只给 provider 与 voice_id（口径同 characters.public_voice_ref）：
        params 是账号侧调参，不公开。"""
        ref = self.payload.get("voice_ref")
        if not isinstance(ref, dict):
            return None
        voice_id = str(ref.get("voice_id") or "").strip()
        if not voice_id:
            return None
        return {"provider": str(ref.get("provider") or "volcengine").strip(), "voice_id": voice_id}

    @property
    def thumbnail(self) -> str:
        return str(self.payload.get("thumbnail") or "")

    @property
    def effects(self) -> list[Any]:
        value = self.payload.get("effects")
        return list(value) if isinstance(value, list) else []

    @property
    def stickers(self) -> list[Any]:
        value = self.payload.get("stickers")
        return list(value) if isinstance(value, list) else []


@dataclass(frozen=True, slots=True)
class HerBinding:
    role_id: str
    her_id: str
    is_default: bool


class SqlHerPackStore:
    """ca_her_pack / ca_character_her 的 SQL 实现。单语句读走 autocommit（同 packs.py）。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def load(self, her_id: str) -> HerPackRecord | None:
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(her_pack).where(her_pack.c.her_id == her_id))
                   ).mappings().first()
        return _record(row) if row is not None else None

    async def list_records(self, *, status: str | None = None) -> list[HerPackRecord]:
        """按 her_id 排序（列表页会缓存，顺序必须稳定）。

        坏行跳过：一张半截 payload 不该把整个 her 列表页挡掉（与 packs 同一口径）。
        """
        stmt = select(her_pack).order_by(her_pack.c.her_id)
        if status:
            stmt = stmt.where(her_pack.c.status == status)
        async with self._auto.connect() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [rec for row in rows if (rec := _record(row)) is not None]

    async def upsert(self, *, her_id: str, renderer: str, payload: dict[str, Any],
                     status: str, source: str) -> HerPackRecord:
        """写入一个 her 包；内容变了 pack_version +1，没变不写。

        播种会反复跑（部署、Hermes 产线重发），幂等是前提：否则每次部署都凭空顶
        版本号，对账时看不出「这个包真改过」。payload 结构不合法当场拒绝——
        写入口严进，读路径才宽出。status 变算内容变（上线/撤回要对账得到）。
        """
        validate_payload(payload)
        if status not in HER_STATUSES:
            raise ValueError(f"unknown her status: {status}")
        now = datetime.now(UTC)
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(her_pack).where(her_pack.c.her_id == her_id))
                   ).mappings().first()
            if row is None:
                await conn.execute(insert(her_pack).values(
                    her_id=her_id, renderer=renderer, payload=payload, status=status,
                    source=source, pack_version=1, created_at=now, updated_at=now))
                version = 1
            else:
                unchanged = (dict(row["payload"] or {}) == payload
                             and (row["renderer"] or "") == renderer
                             and (row["status"] or "") == status)
                version = row["pack_version"]
                if not unchanged:
                    version += 1
                    await conn.execute(update(her_pack)
                                       .where(her_pack.c.her_id == her_id)
                                       .values(renderer=renderer, payload=payload, status=status,
                                               source=source, pack_version=version, updated_at=now))
        return HerPackRecord(her_id=her_id, renderer=renderer, pack_version=version,
                             payload=payload, status=status, source=source)

    # ---- 绑定 ----------------------------------------------------------------

    async def bind(self, *, role_id: str, her_id: str, is_default: bool = True) -> None:
        """绑定角色与 her。重复绑定同一对不写；改 is_default 才写。"""
        now = datetime.now(UTC)
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(character_her)
                                      .where(character_her.c.role_id == role_id,
                                             character_her.c.her_id == her_id))
                   ).mappings().first()
            if row is None:
                await conn.execute(insert(character_her).values(
                    role_id=role_id, her_id=her_id, is_default=is_default,
                    created_at=now, updated_at=now))
            elif bool(row["is_default"]) != is_default:
                await conn.execute(update(character_her)
                                   .where(character_her.c.role_id == role_id,
                                          character_her.c.her_id == her_id)
                                   .values(is_default=is_default, updated_at=now))

    async def default_her_id(self, role_id: str) -> str | None:
        """该角色的默认 her。多条默认（脏数据）取 her_id 最小的一条，保证稳定。"""
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(character_her.c.her_id)
                                      .where(character_her.c.role_id == role_id,
                                             character_her.c.is_default == True)  # noqa: E712
                                      .order_by(character_her.c.her_id))
                   ).first()
        return row[0] if row else None

    async def bindings(self, role_id: str) -> list[HerBinding]:
        async with self._auto.connect() as conn:
            rows = (await conn.execute(select(character_her)
                                       .where(character_her.c.role_id == role_id)
                                       .order_by(character_her.c.her_id))
                    ).mappings().all()
        return [HerBinding(role_id=r["role_id"], her_id=r["her_id"],
                           is_default=bool(r["is_default"])) for r in rows]


def _record(row) -> HerPackRecord | None:
    payload = row["payload"]
    if not isinstance(payload, dict):
        return None
    return HerPackRecord(her_id=row["her_id"], renderer=row["renderer"] or "",
                         pack_version=row["pack_version"], payload=payload,
                         status=row["status"] or "draft", source=row["source"] or "")


async def seed_from_cards(store: SqlHerPackStore, cards: dict[str, Any]) -> tuple[list[str], list[str]]:
    """把角色链里的 ``model_ref`` 转成 her 包 + 默认绑定。返回 (播种的绑定, 跳过的角色)。

    第一刀的桥：现有角色（linche、sudai…）的呈现信息一直住在卡里的映射形
    ``model_ref``（renderer+asset），这里把它注册成独立呈现实体：
    her_id = ``<renderer>-<asset>``（asset 缺失用 role_id）。此后「换形象不换人格」
    只改绑定，不动卡。字符串 model_ref（历史形态 "default-chat"）不是呈现声明，
    与 ``renderer_of`` 同一口径跳过。幂等规则由 ``upsert``/``bind`` 保证。
    """
    seeded: list[str] = []
    skipped: list[str] = []
    for role_id, card in sorted(cards.items()):
        ref = getattr(card, "model_ref", None)
        renderer = ""
        if isinstance(ref, dict):
            renderer = str(ref.get("renderer") or "").strip()
        asset = str(ref.get("asset") or "").strip() if isinstance(ref, dict) else ""
        if not renderer and not asset:
            skipped.append(role_id)
            continue
        her_id = f"{renderer}-{asset or role_id}"
        payload: dict[str, Any] = {
            "name": getattr(card, "name", "") or her_id,
            "tagline": getattr(card, "tagline", "") or "",
            "model_ref": dict(ref),
        }
        card_voice = getattr(card, "voice_ref", None)
        if isinstance(card_voice, dict) and card_voice.get("voice_id"):
            payload["voice_ref"] = dict(card_voice)
        await store.upsert(her_id=her_id, renderer=renderer, payload=payload,
                           status="published", source="card")
        await store.bind(role_id=role_id, her_id=her_id, is_default=True)
        seeded.append(f"{role_id}->{her_id}")
    return seeded, skipped
