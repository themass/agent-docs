"""MCP：连什么。

分界线很清楚：

- **内部能力走进程内接口**（记忆、事件、角色）。绕一层 MCP 只是多一跳延迟，
  而且这些数据本来就在我们手里。
- **外部系统走 MCP**（日历、邮件、健康数据）。它们的鉴权、配额、可用性都不由
  我们控制，用 MCP 把它们隔离在适配层，某个系统挂掉不会拖垮对话。

LiveKit Agents 自带 MCP 客户端（SSE / streamable HTTP），把 server 挂成 toolset
就能给 agent 用。这一层只做配置与安全策略，不重复实现客户端。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Transport(str, Enum):
    # SSE 正在被弃用，新接入优先 streamable HTTP。
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"


@dataclass(frozen=True)
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


# 永远不给模型的工具：文件与进程访问。它们能把整台机器变成模型的攻击面。
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


@dataclass
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


def build_toolsets(registry: McpRegistry) -> list:
    """构造 LiveKit 的 MCPToolset 列表。

    livekit-agents 只在调用时导入：没有它时 HTTP 接口与测试照常工作，
    只有真的要连外部系统的那一刻才需要这个依赖。
    """
    try:
        from livekit.agents.llm.mcp import MCPServerHTTP, MCPToolset
    except ImportError as exc:
        raise RuntimeError(
            "MCP 需要 livekit-agents[mcp]：pip install 'livekit-agents[mcp]'"
        ) from exc

    toolsets = []
    for spec in registry.specs():
        server = MCPServerHTTP(
            url=spec.url,
            transport_type=spec.transport.value,
            client_session_timeout_seconds=spec.timeout_seconds,
        )
        toolsets.append(MCPToolset(id=spec.name, mcp_server=server))
    return toolsets
