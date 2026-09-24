# Claude Agent SDK (Python) 架构分析总结

> **分析对象**: claude-agent-sdk v0.2.88（bundled CLI v2.1.161）  
> **分析时间**: 2026-06-04  
> **分析方法**: 源码深度阅读  
> **源码路径**: `claude-agent-sdk-python/src/claude_agent_sdk`

---

## 文档集

| 文档 | 内容 |
|------|------|
| [CLAUDE_AGENT_SDK_ARCHITECTURE_INDEX.md](./CLAUDE_AGENT_SDK_ARCHITECTURE_INDEX.md) | 索引与快速查找 |
| [CLAUDE_AGENT_SDK_ARCHITECTURE_PART1.md](./CLAUDE_AGENT_SDK_ARCHITECTURE_PART1.md) | 设计哲学、分层架构、控制协议、核心 API |
| [CLAUDE_AGENT_SDK_ARCHITECTURE_PART2.md](./CLAUDE_AGENT_SDK_ARCHITECTURE_PART2.md) | Hooks、MCP、Session、Subagent、权限 |
| [CLAUDE_AGENT_SDK_ARCHITECTURE_DEEP_DIVE.md](./CLAUDE_AGENT_SDK_ARCHITECTURE_DEEP_DIVE.md) | Part 1–3 合并深读 |

---

## 核心发现

### 1. 本质：薄编排层 + 重 CLI

Python SDK **不实现 Agent 循环**。真正的 model↔tools↔subagents 循环在 **Claude Code CLI 子进程** 内。SDK 负责：

- spawn CLI、构建 argv
- stdin/stdout **stream-json** 协议
- **控制平面**：hooks、can_use_tool、SDK MCP、initialize handshake
- 消息解析 → 强类型 `Message`

### 2. 双 API 模型

| API | 模式 | 适用 |
|-----|------|------|
| `query()` | 单向、一次性 | 脚本、批处理 |
| `ClaudeSDKClient` | 双向、多轮 | hooks、自定义 tool、interrupt |

### 3. 与 OpenAI Agents SDK 对照

| 维度 | OpenAI Agents SDK | Claude Agent SDK |
|------|-------------------|------------------|
| Loop 位置 | Python `run_loop.py` | CLI 二进制 |
| 工具 | Python function_tool | CLI 内置 + SDK MCP |
| 多 Agent | Handoff | Agent tool + AgentDefinition |
| Session | Session 类 | JSONL + SessionStore 镜像 |
| 扩展点 | Guardrail、MCP client | Hooks、SDK MCP server |

### 4. 源码规模

| 模块 | 文件 | ~行数 |
|------|------|-------|
| 控制协议 | `_internal/query.py` | ~900 |
| CLI Transport | `_internal/transport/subprocess_cli.py` | ~760 |
| 公共 Client | `client.py` | ~400+ |
| 类型定义 | `types.py` | ~1900+ |
| 消息解析 | `_internal/message_parser.py` | ~300+ |

---

**文档版本**: v1.0

> **与 OpenAI Agents SDK 对比**：[OPENAI_VS_CLAUDE_AGENT_SDK_COMPARISON.md](../../docs/OPENAI_VS_CLAUDE_AGENT_SDK_COMPARISON.md)
