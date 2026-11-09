"""记忆接口规范 v1 —— 代码形式的唯一定义。

完整规范（语义、错误、删除、一致性、召回排序、一致性测试要求）见
``docs/chat-agent-memory-spec.md``。任何记忆后端只要满足该规范，就可以替换，
调用方（app、api、memory_hub）不需要改动。

调用方只依赖这个模块；后端实现放在 ``adapters/``。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

SPEC_VERSION = "1"

MAX_CONTENT_CHARS = 300      # 单条记忆内容上限；超出是调用方错误，后端必须拒绝而不是截断
MAX_BATCH = 50               # 单次 add 的条数上限
MAX_LIST_LIMIT = 100         # list_for_user 的 limit 上限
MAX_SEARCH_LIMIT = 20        # search 的 limit 上限


class MemoryBaseError(Exception):
    """记忆接口的基类异常。"""


class MemoryInvalid(MemoryBaseError, ValueError):
    """调用方参数不合法（内容过长、批量过大、用户 id 非法等）。"""


class MemoryUnavailable(MemoryBaseError):
    """后端暂时不可用。调用方可以重试；不得据此认为数据已丢失。"""


class MemoryKind(str, Enum):
    """记忆类型。跨后端保持这些字符串值不变（规范 §2.2）。"""

    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    EVENT = "EVENT"


# 模型输出的 kind 不可控：接受大小写、单复数与中文别名，认不出时由调用方决定默认值。
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
    """把任意输入收敛到 MemoryKind；认不出返回 None。"""
    if isinstance(value, MemoryKind):
        return value
    if not isinstance(value, str):
        return None
    return _KIND_ALIASES.get(value.strip().casefold())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryItem:
    """一条用户记忆（规范 §2.1）。

    - ``id``：后端分配。调用方写入前可以留空；返回值中必然非空。
    - ``score``：只在 search 结果中有意义（越大越相关）；写入与列表返回 None。
    - ``source_character_id`` / ``source_message_id``：审计字段，后端必须原样保存并返回。
    """

    id: str
    content: str
    kind: MemoryKind = MemoryKind.FACT
    source_character_id: str = ""
    source_message_id: str = ""
    created_at: datetime = field(default_factory=utc_now)
    score: float | None = None


def validate_content(content: str) -> None:
    if not isinstance(content, str) or not content.strip():
        raise MemoryInvalid("content must be a non-empty string")
    if len(content) > MAX_CONTENT_CHARS:
        raise MemoryInvalid(f"content exceeds {MAX_CONTENT_CHARS} characters")


def validate_user_id(user_id: str) -> None:
    """user_id 是复合 ``app:uid``（memory_hub 生成）或裸 uid：非空，且至多一个冒号。"""
    if not isinstance(user_id, str) or not user_id or user_id.count(":") > 1:
        raise MemoryInvalid("user_id must be a non-empty string with at most one ':'")


class MemoryPort(Protocol):
    """记忆接口 v1。所有方法以 ``user_id`` 为隔离边界（规范 §3）。

    方法都是异步的：同步客户端由适配层放进线程。
    """

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        """写入一批；返回后端确认后的条目（id 与 created_at 以后端为准）。原子：要么全写，要么全不写。"""
        ...

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        kinds: Iterable[MemoryKind] | None = None,
    ) -> list[MemoryItem]:
        """按查询召回，最多 ``limit`` 条。``kinds`` 为空表示不过滤。排序见规范 §5。"""
        ...

    async def list_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[MemoryItem]:
        """按 created_at 倒序分页列出（规范 §4）。"""
        ...

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        """删除单条。不存在或不属于该用户返回 False，二者对调用方不可区分（规范 §6）。"""
        ...

    async def delete_user(self, user_id: str) -> int:
        """删除该用户的全部记忆，返回删除条数。删除是否完整以 ``list_for_user`` 为空为准（规范 §6）。"""
        ...
