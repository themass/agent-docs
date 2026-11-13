"""MCP 外部 server 的配置、白名单与熔断（T §3）。纯逻辑。

白名单默认拒绝：allow_tools 为空表示一个都不挂（与旧实现相反，见 T §3.3）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class Transport(str, Enum):
    # SSE 已被 MCP 规范弃用，新接入一律 streamable HTTP。
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"


@dataclass(frozen=True)
class McpServerSpec:
    name: str
    url: str
    transport: Transport = Transport.STREAMABLE_HTTP
    allow_tools: frozenset[str] = frozenset()       # 空 = 全部拒绝
    tool_permission: Mapping[str, str] = field(default_factory=dict)  # 每个工具的权限
    default_permission: str = "confirm"             # 未声明的工具一律需要确认
    products: frozenset[str] = frozenset({"chat", "roleplay"})
    timeout_seconds: float = 8.0
    auth_env: str | None = None                     # 凭据只从环境变量读


FORBIDDEN_TOOL_PATTERNS = (
    "read_file",
    "write_file",
    "edit_file",
    "delete_file",
    "list_dir",
    "shell",
    "exec",
    "subprocess",
)


def is_forbidden_tool(name: str) -> bool:
    lowered = name.lower()
    return any(pattern in lowered for pattern in FORBIDDEN_TOOL_PATTERNS)


def filter_tools(spec: McpServerSpec, names: list[str]) -> list[str]:
    """两道过滤：白名单决定「要不要」，禁用规则决定「能不能」。白名单为空则全部拒绝。"""
    return [n for n in names if n in spec.allow_tools and not is_forbidden_tool(n)]


def permission_of(spec: McpServerSpec, tool: str) -> str:
    return spec.tool_permission.get(tool, spec.default_permission)


@dataclass
class CircuitBreaker:
    """连续失败达到阈值后打开，冷却期内该 server 的工具从白名单移除（T §3.5）。"""

    threshold: int = 5
    cooldown_s: float = 60.0
    failures: int = 0
    opened_at: float | None = None

    def available(self, now: float) -> bool:
        if self.opened_at is None:
            return True
        return now - self.opened_at >= self.cooldown_s

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self, now: float) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = now


@dataclass
class McpRegistry:
    _servers: dict[str, McpServerSpec] = field(default_factory=dict)

    def add(self, spec: McpServerSpec) -> None:
        if spec.name in self._servers:
            raise ValueError(f"duplicate mcp server: {spec.name}")
        self._servers[spec.name] = spec

    def get(self, name: str) -> McpServerSpec | None:
        return self._servers.get(name)

    def specs(self) -> list[McpServerSpec]:
        return list(self._servers.values())

    def names(self) -> list[str]:
        return list(self._servers)
