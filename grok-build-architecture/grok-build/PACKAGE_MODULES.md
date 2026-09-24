# Grok Build — Crate / 模块索引

> **版本**: 4.0 · 与 [ARCHITECTURE.md](./ARCHITECTURE.md) 配套

> Workspace 约 **80** 个 members（`Cargo.toml` workspace）。按职责分组，便于定位源码。

---

## 1. 入口与组合

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-pager-bin` | `crates/codegen/xai-grok-pager-bin` | 主二进制 `grok` |
| `xai-grok-pager` | `crates/codegen/xai-grok-pager` | TUI 应用 |
| `xai-grok-pager-render` | `crates/codegen/xai-grok-pager-render` | ratatui 渲染 |
| `xai-grok-pager-npm` | `crates/codegen/xai-grok-pager/npm/` | npm 分发包装 |

---

## 2. 运行时与 Session

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-shell` | `crates/codegen/xai-grok-shell` | Session、ACP、Leader、Headless |
| `xai-grok-agent` | `crates/codegen/xai-grok-agent` | Agent、AgentBuilder、定义解析 |
| `xai-chat-state` | `crates/codegen/xai-chat-state` | 对话状态 Actor、流式 UI 状态 |
| `xai-acp-lib` | `crates/common/xai-acp-lib` | ACP 协议类型与传输 |

---

## 3. 工具与 Hub

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-tools` | `crates/codegen/xai-grok-tools` | ToolBridge、registry、内置工具 |
| `xai-tool-protocol` | `crates/common/xai-tool-protocol` | 工具 schema、ToolKind |
| `xai-tool-runtime` | `crates/common/xai-tool-runtime` | 工具执行运行时抽象 |
| `xai-computer-hub-sdk` | `crates/common/xai-computer-hub-sdk` | Hub RPC、`ToolHarness` |
| `xai-grok-workspace` | `crates/codegen/xai-grok-workspace` | FS、权限、checkpoint、hub_server |
| `xai-grok-sandbox` | `crates/codegen/xai-grok-sandbox` | 沙箱执行（若启用） |

---

## 4. Memory 与压缩

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-memory` | `crates/codegen/xai-grok-memory` | 跨 session 记忆、FTS、向量 |
| `xai-grok-compaction` | `crates/common/xai-grok-compaction` | 上下文压缩策略 |
| `xai-grok-compaction-common` | `crates/common/xai-grok-compaction-common` | 压缩共享类型 |

---

## 5. MCP 与工作流

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-mcp` | `crates/codegen/xai-grok-mcp` | MCP 客户端/服务端集成 |
| `xai-workflow` | `crates/codegen/xai-workflow` | Rhai 工作流引擎 |
| `xai-workflow-types` | `crates/codegen/xai-workflow-types` | 工作流类型定义 |

---

## 6. 模型与聊天代理

| Crate | 路径 | 说明 |
|-------|------|------|
| `prod/mc` 相关 | `prod/mc/` | 聊天代理、模型路由类型 |
| `xai-grok-chat-proxy` | `crates/codegen/`（若存在） | 模型 API 代理层 |

（具体 member 名以 `Cargo.toml` 为准；同步后可能有增减。）

---

## 7. Telemetry 与配置

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-grok-telemetry` | `crates/codegen/xai-grok-telemetry` | unified_log、指标 |
| `xai-grok-config` | `crates/codegen/xai-grok-config` | 全局/项目配置 |

---

## 8. 构建与代码生成

| Crate | 路径 | 说明 |
|-------|------|------|
| `xai-build` | `crates/build/` | 构建脚本、proto codegen |
| `third_party/` | `third_party/` | Mermaid 等 vendored 依赖 |

---

## 9. 按任务找 crate

| 我要改… | 先看 |
|---------|------|
| CLI 子命令 | `xai-grok-pager-bin` |
| 界面/快捷键 | `xai-grok-pager` + `pager-render` |
| Turn 循环/取消 | `xai-grok-shell/.../run_loop.rs`, `turn.rs` |
| Agent prompt/工具列表 | `xai-grok-agent`, `.grok/agents/` |
| 新内置工具 | `xai-grok-tools` + `tool-protocol` |
| 文件权限/YOLO | `xai-grok-workspace` |
| 记忆检索/Dream | `xai-grok-memory`, `memory_dream.rs` |
| 上下文太长 | `xai-grok-compaction`, `xai-chat-state` |
| IDE 集成 | `xai-acp-lib`, `agent_mode` |
| MCP 服务器 | `xai-grok-mcp` |
| 自动化脚本流 | `xai-workflow` |

---

## 10. 同步说明

- 根 `Cargo.toml` 多为 **自动生成**，手改易在下次 sync 丢失。
- 功能开发通常在上游 monorepo 完成，再同步到 `grok-build`。
- 阅读前确认 `SOURCE_REV` 与本地分支是否一致。
