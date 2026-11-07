"""MCP：连接外部系统（日历、邮件、健康数据）。

内部能力（记忆、事件、角色）走进程内接口，不绕 MCP——多一跳只加延迟。
外部系统的鉴权、配额、可用性不由我们控制，用 MCP 隔离在适配层。
"""

from companion.mcp.registry import (
    FORBIDDEN_TOOL_PATTERNS,
    McpRegistry,
    McpServerSpec,
    Transport,
    build_toolsets,
    filter_tools,
    is_forbidden_tool,
)

__all__ = [
    "FORBIDDEN_TOOL_PATTERNS",
    "McpRegistry",
    "McpServerSpec",
    "Transport",
    "build_toolsets",
    "filter_tools",
    "is_forbidden_tool",
]
