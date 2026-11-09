"""记忆接口。

记忆的主键是**用户**，不是角色：同一用户的所有角色共享一份记忆，每条记忆记录
来源角色与来源消息，客户端「我记住的」页面靠这两个字段标注出处。

这个模块只有协议与数据形状，不含任何后端。v1 后端是 mem0（见 ``mem0.py``），
Hindsight 作为备选接在同一个端口后面，替换实现不改上层。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol


class MemoryKind(str, Enum):
    """记忆的类型；写进后端 metadata，跨后端保持字符串形状。"""

    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    EVENT = "EVENT"


# 模型输出的 kind 不可控：接受大小写、单复数与中文别名，认不出时按 FACT 处理。
_KIND_ALIASES: dict[str, MemoryKind] = {
    "fact": MemoryKind.FACT,
    "facts": MemoryKind.FACT,
    "事实": MemoryKind.FACT,
    "preference": MemoryKind.PREFERENCE,
    "preferences": MemoryKind.PREFERENCE,
    "prefer": MemoryKind.PREFERENCE,
    "偏好": MemoryKind.PREFERENCE,
    "event": MemoryKind.EVENT,
    "events": MemoryKind.EVENT,
    "事件": MemoryKind.EVENT,
}


def coerce_kind(value: object) -> MemoryKind | None:
    """把任意输入收敛到 MemoryKind；认不出返回 None，由调用方决定默认值。"""
    if isinstance(value, MemoryKind):
        return value
    if not isinstance(value, str):
        return None
    return _KIND_ALIASES.get(value.strip().casefold())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryItem:
    """一条用户记忆。

    ``id`` 由后端分配；写入前用本地 uuid 占位。``score`` 只对检索结果有意义，
    写入与列表场景为 None。``source_character_id`` / ``source_message_id`` 是
    审计字段：删角色、查来源都靠它们，任何后端适配都必须原样带回来。
    """

    id: str
    content: str
    kind: MemoryKind = MemoryKind.FACT
    source_character_id: str = ""
    source_message_id: str = ""
    created_at: datetime = field(default_factory=utc_now)
    score: float | None = None


class MemoryPort(Protocol):
    """记忆后端的统一入口。

    所有方法都以 ``user_id`` 为隔离边界；实现必须保证不同用户互相不可见。
    这些方法是异步的：mem0 是同步客户端，适配层负责丢进线程。
    """

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        """写入一批记忆，返回后端确认后的条目（id 以后端为准）。"""
        ...

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryItem]:
        """按当前话题召回，``score`` 越大越相关。"""
        ...

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        """删除单条；不存在、不属于该用户都返回 False。"""
        ...

    async def delete_user(self, user_id: str) -> int | None:
        """删除该用户全部记忆（含索引与原始抽取记录）。

        返回删除条数；后端不报告条数时返回 None。删除是否干净以后面
        ``list_for_user`` 为空为准，不能只看返回值。
        """
        ...

    async def list_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[MemoryItem]:
        """按时间倒序列出该用户的记忆，供「我记住的」页面分页。"""
        ...
