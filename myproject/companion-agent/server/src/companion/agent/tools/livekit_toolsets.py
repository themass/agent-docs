from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from companion.agent.tools.mcp_policy import McpRegistry


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
