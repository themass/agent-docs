from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Transport(str, Enum):
    # SSE 正在被弃用，新接入优先 streamable HTTP。
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"


class McpServerSpec:
    """一个外部 MCP server 的配置。"""

    name: str
    url: str
    transport: Transport = Transport.STREAMABLE_HTTP
    # 只暴露这些工具。空集合表示全部——但默认应该是白名单，不是黑名单。
    allow_tools: frozenset[str] = field(default_factory=frozenset)
    timeout_seconds: float = 60.0
    # 鉴权凭据从环境变量读，不进配置。
    auth_env: str | None = None
    # 对外部系统的写操作默认要确认。读操作可以放开。
    write_requires_confirm: bool = True


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
    """按白名单与禁用规则过滤。

    两道都要过：白名单决定「要不要」，禁用规则决定「能不能」。一个外部 server
    即使把 read_file 列进白名单，也不会被挂上。
    """
    allowed = spec.allow_tools
    return [
        name
        for name in names
        if not is_forbidden_tool(name) and (not allowed or name in allowed)
    ]


class McpRegistry:
    """登记外部 MCP server。装配层从这里取配置去建 toolset。"""

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
