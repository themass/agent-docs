"""工具调用的纯判定：授权结论、参数指纹、结果截断（T §2.3、§2.5）。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from enum import Enum

from companion.tools.spec import Permission, ToolSpec


class Verdict(str, Enum):
    NOT_AVAILABLE = "not_available"      # 不在本回合白名单，或工具不存在：不执行
    INVALID_ARGS = "invalid_args"        # 参数不合法：让模型改
    CONFIRM = "needs_confirmation"       # 需要用户确认：只建记录，不执行
    EXECUTE = "execute"                  # 直接执行


def authorize(spec: ToolSpec | None, allowed: frozenset[str], args_valid: bool) -> Verdict:
    """授权顺序固定（T §2.3）：白名单 → 参数 → 权限。权限来自注册表，模型无法改变。"""
    if spec is None or spec.name not in allowed:
        return Verdict.NOT_AVAILABLE
    if not args_valid:
        return Verdict.INVALID_ARGS
    if spec.permission is Permission.CONFIRM:
        return Verdict.CONFIRM
    return Verdict.EXECUTE


def fingerprint(name: str, args: dict) -> str:
    """参数指纹：sha256 前 16 位。审计只存指纹，不存原文（T §2.5）。"""
    canonical = json.dumps({"tool": name, "args": args}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def truncate(text: str, budget: int) -> tuple[str, bool]:
    if len(text) <= budget:
        return text, False
    return text[: max(0, budget - 1)] + "…", True


def allowed_for(product: str, specs: Iterable[ToolSpec], names: Iterable[str]) -> frozenset[str]:
    """本回合白名单 = 产品允许 ∩ 声明的名称（T §2.3）。"""
    wanted = set(names)
    return frozenset(s.name for s in specs if product in s.products and s.name in wanted)
