"""mem0 记忆后端适配（v1）。

``mem0ai`` 不在 import 期导入：没装它的环境（单测、纯路由进程）照常 import 本模块，
只有真的要建客户端时才 import，失败抛 [`Mem0Unavailable`]。

期望的客户端接口（mem0 的 ``Memory`` 与其异步版都满足）::

    add(messages, *, user_id, metadata, infer=...)   -> {"results": [{...}]} | list
    search(query, *, user_id, limit, ...)            -> [{"id","memory","score","metadata"}]
    get_all(*, user_id, limit, offset, ...)          -> {"results": [...]}
    get(memory_id)                                   -> {"id","memory","user_id","metadata"} 可缺
    delete(memory_id=...)                            -> 任意
    delete_all(*, user_id=...)                       -> 任意

同步客户端会被丢进线程执行，异步客户端直接 await，两者都能接。

**用户隔离**靠每次调用都带 ``user_id``。mem0 的 ``delete`` 按 id 删、不校验归属，
所以 ``delete_one`` 先读一次条目核对 ``user_id``；客户端没有 ``get`` 时退化为直接
删除，这一点在 limitations 里明说。

**账号删除**不依赖 ``delete_all`` 的语义：先按 id 逐条删（``delete`` 同时清向量
与记录），再调 ``delete_all`` 兜历史表等枚举不到的部分。账号删除是低频路径，
宁可多打 N 次接口，也不接受「可能没删干净」。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from companion.ports.memory import MemoryItem, MemoryKind, coerce_kind, utc_now

logger = logging.getLogger(__name__)

# mem0 metadata 实际按字符串存；统一走字符串，避免不同后端把 datetime 转坏。
META_CHARACTER = "source_character_id"
META_MESSAGE = "source_message_id"
META_KIND = "kind"
META_CREATED_AT = "created_at"

# 枚举时每页条数。mem0 的 get_all 支持 limit/offset，但个别版本会忽略 offset，
# 所以翻页按 id 去重，宁可少翻也不错翻。
_PAGE = 200
_MAX_ROWS = 10_000


class Mem0Unavailable(RuntimeError):
    """mem0ai 未安装，或客户端构造失败。"""


def available() -> bool:
    """探测 mem0ai 是否可导入；不建客户端，不读配置。"""
    try:
        import mem0  # noqa: F401
    except ImportError:
        return False
    return True


def _require_user(user_id: str) -> str:
    """空 user_id 在 mem0 里等于「不筛用户」，账号删除会误伤全部数据。"""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required")
    return user_id


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call(method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """调用可能是同步也可能是异步的方法。

    同步路径用 ``to_thread``：mem0 内部会打 HTTP/向量库，阻塞事件循环不可接受。
    """
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    result = await asyncio.to_thread(method, *args, **kwargs)
    return await _maybe_await(result)


def _rows(payload: Any) -> list[dict[str, Any]]:
    """把 mem0 的两种返回形状（list / {"results": [...]}）归一。"""
    if payload is None:
        return []
    if isinstance(payload, dict):
        for key in ("results", "memories", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
        # 单条记录也当一行处理
        return [payload] if payload.get("id") or payload.get("memory") else []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def _parse_created_at(value: Any, *, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return default or utc_now()


def _build_client(config: dict[str, Any] | None) -> Any:
    """延迟 import mem0ai 并建客户端。

    配置里的密钥一律来自环境变量（mem0 自己读 ``OPENAI_API_KEY`` 等），这里不接受
    调用方塞密钥的写法，免得密钥进了代码或配置文件。
    """
    try:
        from mem0 import Memory
    except ImportError as exc:
        raise Mem0Unavailable(
            "mem0ai 未安装：pip install mem0ai，或用 Mem0MemoryPort(client=...) 注入客户端"
        ) from exc
    try:
        return Memory.from_config(config) if config else Memory()
    except Exception as exc:  # noqa: BLE001 - 构造失败的原因千奇百怪，统一收口
        raise Mem0Unavailable(f"mem0 客户端构造失败：{exc}") from exc


class Mem0MemoryPort:
    """把 mem0 客户端包成 ``MemoryPort``。

    ``infer=True`` 时会走 mem0 自己的 LLM 抽取（多一次模型调用、还要模型配置）。
    我们的抽取已经在 ``extraction.py`` 做过，所以默认 ``infer=False``，mem0 只当
    存储与向量检索用。

    ``client`` 省略时才去建真客户端；测试与离线链路直接注入。
    """

    def __init__(
        self,
        client: Any | None = None,
        *,
        infer: bool = False,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._client = client if client is not None else _build_client(config)
        self._infer = infer

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        _require_user(user_id)
        stored: list[MemoryItem] = []
        for item in items:
            payload = await _call(
                self._client.add,
                [{"role": "user", "content": item.content}],
                user_id=user_id,
                metadata=_metadata(item),
                infer=self._infer,
            )
            rows = _rows(payload)
            if rows:
                stored.extend(self._to_item(row, fallback=item) for row in rows)
            else:
                # 后端没回显（infer=False 时部分版本如此）就按入参回一份，id 留本地。
                stored.append(item)
        return stored

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryItem]:
        _require_user(user_id)
        payload = await _call(
            self._client.search, query, user_id=user_id, limit=max(1, limit)
        )
        items = [
            self._to_item(row)
            for row in _rows(payload)
            if _belongs_to(row, user_id)
        ]
        return items

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        _require_user(user_id)
        if not memory_id:
            return False
        if not await self._owned_by(user_id, memory_id):
            return False
        await _call(self._client.delete, memory_id=memory_id)
        return True

    async def delete_user(self, user_id: str) -> int | None:
        """账号级删除：逐条删 + 兜底 delete_all。

        mem0 的 ``delete_all(user_id=...)`` 在不同版本里对「原始抽取记录」的处理
        不一致，返回值也不保证。这里不把完整性押在它身上：先枚举并逐条删（``delete``
        同时清向量与记录），再调一次 ``delete_all`` 收掉历史表，最后再枚举一次复核。
        """
        _require_user(user_id)
        try:
            before = len(await self._all_rows(user_id))
        except Exception as exc:  # noqa: BLE001 - 数不出来不代表不能删
            logger.warning("mem0 枚举 %s 的记忆失败：%s", user_id, exc)
            before = None

        await self._drain(user_id)

        try:
            await _call(self._client.delete_all, user_id=user_id)
        except Exception as exc:  # noqa: BLE001 - 已逐条删过，兜底失败不阻断
            logger.warning("mem0 delete_all 失败（已逐条清扫）：%s", exc)

        # delete_all 之后可能还有它删不掉的残余；再扫一轮，空转即停。
        await self._drain(user_id)
        return before

    async def list_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[MemoryItem]:
        _require_user(user_id)
        payload = await _call(
            self._client.get_all,
            user_id=user_id,
            limit=max(1, limit),
            offset=max(0, offset),
        )
        items = [
            self._to_item(row) for row in _rows(payload) if _belongs_to(row, user_id)
        ]
        # mem0 不保证顺序；「我记住的」按时间倒序展示。
        items.sort(key=lambda i: i.created_at, reverse=True)
        return items

    async def purge_ok(self, user_id: str) -> bool:
        """删除后的零残留复核；测试与删除账号流程共用。"""
        _require_user(user_id)
        return len(await self._all_rows(user_id)) == 0

    async def _all_rows(self, user_id: str) -> list[dict[str, Any]]:
        """翻完该用户的全部条目。

        ``delete_user`` 的完整性靠这份枚举，所以这里必须真的翻到底，而不是取一页
        就当全部。按 id 去重是因为部分 mem0 版本会忽略 offset。
        """
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        while len(rows) < _MAX_ROWS:
            payload = await _call(
                self._client.get_all, user_id=user_id, limit=_PAGE, offset=offset
            )
            batch = _rows(payload)
            fresh = [r for r in batch if str(r.get("id") or "") not in seen]
            if not fresh:
                break
            for row in fresh:
                seen.add(str(row.get("id") or ""))
            rows.extend(fresh)
            offset += len(batch)
            if len(batch) < _PAGE:
                break
        if len(rows) >= _MAX_ROWS:
            logger.warning("mem0 用户 %s 条目超过 %d，枚举已截断", user_id, _MAX_ROWS)
        return rows

    async def _drain(self, user_id: str) -> int:
        """按 id 删除该用户能枚举到的所有条目，返回删掉的条数。

        一轮没删掉任何东西就停：后端拒绝删除时重复调用只会空转。
        """
        removed = 0
        for _ in range(5):
            try:
                rows = await self._all_rows(user_id)
            except Exception as exc:  # noqa: BLE001 - 枚举失败交给下一轮/兜底
                logger.warning("mem0 清扫 %s 时枚举失败：%s", user_id, exc)
                break
            if not rows:
                break
            deleted = 0
            for row in rows:
                memory_id = row.get("id")
                if not memory_id:
                    continue
                try:
                    await _call(self._client.delete, memory_id=str(memory_id))
                    deleted += 1
                except Exception as exc:  # noqa: BLE001 - 单条失败不放弃其余
                    logger.warning("mem0 删除 %s 失败：%s", memory_id, exc)
            removed += deleted
            if deleted == 0:
                break
        return removed

    async def _owned_by(self, user_id: str, memory_id: str) -> bool:
        getter = getattr(self._client, "get", None)
        if getter is None:
            return True
        row = await _call(getter, memory_id)
        rows = _rows(row)
        if not rows:
            return False
        owner = rows[0].get("user_id")
        return owner is None or str(owner) == user_id

    def _to_item(
        self, row: dict[str, Any], *, fallback: MemoryItem | None = None
    ) -> MemoryItem:
        meta = row.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
        content = row.get("memory") or row.get("content") or row.get("text")
        if not isinstance(content, str) or not content:
            content = fallback.content if fallback else ""
        raw_score = row.get("score")
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        return MemoryItem(
            id=str(row.get("id") or (fallback.id if fallback else "")),
            content=content,
            kind=coerce_kind(meta.get(META_KIND)) or MemoryKind.FACT,
            # 来源字段是审计信息：后端丢了就退回入参，不能变成空串。
            source_character_id=str(
                meta.get(META_CHARACTER)
                or (fallback.source_character_id if fallback else "")
            ),
            source_message_id=str(
                meta.get(META_MESSAGE)
                or (fallback.source_message_id if fallback else "")
            ),
            # metadata 里是我们写入时的语义时间；行级 created_at 是后端插入时间，
            # 导入/回填会把它冲掉，所以前者优先。
            created_at=_parse_created_at(
                meta.get(META_CREATED_AT) or row.get("created_at"),
                default=fallback.created_at if fallback else None,
            ),
            score=score,
        )


def _belongs_to(row: dict[str, Any], user_id: str) -> bool:
    """后端漏了过滤时在本地再拦一道；mem0 云端配错 filters 会跨用户返回。"""
    owner = row.get("user_id")
    return owner is None or str(owner) == user_id


def _metadata(item: MemoryItem) -> dict[str, str]:
    """我们的字段 → mem0 metadata；字符串值才能跨版本稳定往返。"""
    return {
        META_CHARACTER: item.source_character_id,
        META_MESSAGE: item.source_message_id,
        META_KIND: item.kind.value,
        META_CREATED_AT: item.created_at.isoformat(),
    }


__all__ = [
    "Mem0MemoryPort",
    "Mem0Unavailable",
    "available",
    "META_CHARACTER",
    "META_MESSAGE",
    "META_KIND",
    "META_CREATED_AT",
]
