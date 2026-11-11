"""工具定义（T §2.1–2.2）。纯逻辑：构造期校验，不依赖框架。

构造期规则（违反即拒绝注册，启动失败）：
1. undoable=False 不能是 AUTO；
2. side_effect=EXTERNAL 必须是 CONFIRM（触达外部世界要用户确认）；
3. AUTO 必须有副作用（只读应标 READ）；
4. 名称不能命中禁用模式（read_file、shell、exec…）；
5. 参数模型不能含身份字段（身份只来自上下文，§2.2）；
6. CONFIRM 必须有确认标题。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from companion.domain.tools.mcp_policy import is_forbidden_tool

PRODUCTS = frozenset({"chat", "roleplay"})
IDENTITY_FIELDS = frozenset({"user_id", "owner_id", "role_id", "character_id", "session_id", "turn_id"})
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,47}$")


class ToolSpecError(ValueError):
    """工具定义违反构造期规则。"""


class Permission(str, Enum):
    READ = "read"        # 只读，直接执行
    AUTO = "auto"        # 写自己的数据，直接执行，事后告知
    CONFIRM = "confirm"  # 必须用户确认后才执行


class SideEffect(str, Enum):
    NONE = "none"
    OWN_DATA = "own_data"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ToolContext:
    """处理函数拿到的身份与回合信息。全部来自服务端上下文，模型不能指定。"""

    owner_id: int
    session_id: int
    turn_id: str
    character_id: str
    locale: str
    confirmation_id: str | None = None   # 确认后执行时有值：处理函数据此做幂等（同一确认只生效一次）


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: type               # pydantic 模型，给模型生成 JSON Schema，并在调用前校验
    permission: Permission
    side_effect: SideEffect
    undoable: bool = True
    idempotent: bool = True
    timeout_s: float = 10.0
    result_budget_chars: int = 2000
    products: frozenset[str] = PRODUCTS
    confirm_title: str = ""

    def __post_init__(self) -> None:
        if not NAME_PATTERN.match(self.name):
            raise ToolSpecError(f"tool name must be snake_case: {self.name!r}")
        if is_forbidden_tool(self.name):
            raise ToolSpecError(f"tool name matches a forbidden pattern: {self.name!r}")
        if not self.undoable and self.permission is Permission.AUTO:
            raise ToolSpecError(f"{self.name}: an irreversible tool cannot be AUTO")
        if self.side_effect is SideEffect.EXTERNAL and self.permission is not Permission.CONFIRM:
            raise ToolSpecError(f"{self.name}: EXTERNAL side effects must require CONFIRM")
        if self.permission is Permission.AUTO and self.side_effect is SideEffect.NONE:
            raise ToolSpecError(f"{self.name}: a side-effect-free tool should be READ, not AUTO")
        if self.permission is Permission.CONFIRM and not self.confirm_title.strip():
            raise ToolSpecError(f"{self.name}: CONFIRM tools need a confirm_title")
        if not self.products or not self.products <= PRODUCTS:
            raise ToolSpecError(f"{self.name}: products must be a non-empty subset of {sorted(PRODUCTS)}")
        if self.timeout_s <= 0 or self.result_budget_chars <= 0:
            raise ToolSpecError(f"{self.name}: timeout and result budget must be positive")
        fields = _param_fields(self.params)
        leaked = sorted(fields & IDENTITY_FIELDS)
        if leaked:
            raise ToolSpecError(f"{self.name}: parameters must not carry identity fields {leaked}")


def _param_fields(model: Any) -> set[str]:
    fields = getattr(model, "model_fields", None)
    if fields is None:
        fields = getattr(model, "__annotations__", {})
    return set(fields)
