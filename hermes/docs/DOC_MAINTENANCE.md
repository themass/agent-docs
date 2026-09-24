# 文档维护基准（源码锚点）

> **Hermes 发版**: `0.19.0`（`v2026.7.20`）  
> **核对日期**: 2026-07-31  
> **用途**: 刷新各 `docs/*.md` 时对照；行号随 commit 漂移，以 `rg` / IDE 为准。

---

## Canonical 地图（唯一真相源）

| 域 | Canonical 文件 | 新结论写哪里 |
|----|----------------|--------------|
| 呈现 / 连接 / Skin / Widget | `SURFACE_ARCHITECTURE.md` | 该文件各 § |
| Agent 内核总览 | `ARCHITECTURE.md` | §0 / §4 / §5 / §11.16 |
| Agent 循环 / AIAgent | `AGENT_LOOP_ARCHITECTURE.md` | **该文件**（§10 增量；§12–14 附录） |
| Gateway IM + CLI 交互面 | `CLI_GATEWAY_SYSTEM.md` | §0 入口地图 · §4 Gateway 启动/实体/入出站 · §5 Cron+ACP · §6 Kanban |
| Memory | `MEMORY_SYSTEM.md` | 扁平 §1–§11（三层主模型 → 实现 → 用法 → Provider → 扩展）；勿再拆 Parts |
| Tools | `TOOLS_SYSTEM.md` | 扁平 §1–§14（Registry / 并行 / 预算 / 三大深潜）；勿再拆 Parts |
| HITL 审批 | `HITL_APPROVAL_FLOW.md` | CLI Queue / Gateway Event · pending · §14 与其它项目对比 |
| 多 Agent | `MULTI_AGENT_ARCHITECTURE.md` | 扁平 §1–§16（架构 + 中断/HITL）；已并入原 `SUBAGENT_INTERRUPT_AND_HITL_COMPARISON`；无 Parts |
| Prompt | `PROMPT_SYSTEM_ARCHITECTURE.md` | 扁平 §1–§17（2026-08-03 去重）；全文 dump → `SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md` |
| 版本 | `VERSION_HISTORY.md` | 发版表 +「未发版」 |
| MCP | `MCP_INTEGRATION.md` | 扁平去重版；协议/客户端/OAuth/Sampling |
| Plugins | `PLUGINS_SYSTEM.md` | 架构 · 开发 · 配置 · 加载 · 执行（2026-08-03 重排） |

### 2026-07-31 合并删除（内容已并入 Canonical Parts）

| 已删除 | 并入 |
|--------|------|
| `MEMORY_SYSTEM_OVERVIEW` / `USAGE` / `EVOLUTION` / `EXTERNAL_MEMORY_PROVIDERS` | `MEMORY_SYSTEM.md` |
| `TOOLS_SYSTEM_DEEP` / `TOOLS_COMPLETE_ANALYSIS` | `TOOLS_SYSTEM.md`（2026-07-31 再去重为扁平 §） |
| `GATEWAY_SYSTEM_COMPLETE` | `GATEWAY_SYSTEM.md` → 再并入 `CLI_GATEWAY_SYSTEM.md` |
| `CLI_SYSTEM.md` / `GATEWAY_SYSTEM.md` 正文 | `CLI_GATEWAY_SYSTEM.md`（2026-08-03）；旧文件为跳转 stub |
| `MULTI_AGENT_SYSTEM` | `MULTI_AGENT_ARCHITECTURE.md` |
| `SUBAGENT_INTERRUPT_AND_HITL_COMPARISON` | `MULTI_AGENT_ARCHITECTURE.md` §12 / §16 |
| `PROMPT_SYSTEM` / `PROMPT_COMPLETE_FINAL_CHINESE` / `PARENT_CHILD_PROMPT_COMPARISON` | `PROMPT_SYSTEM_ARCHITECTURE.md`（2026-08-03 再去重为扁平 §1–§17） |
| `AIAgent_ARCHITECTURE` / `AGENT_LOOP_DEEP` / `AGENT_LOOP_DEEP_DIVE` | `AGENT_LOOP_ARCHITECTURE.md`（或 stub） |

勿再 fork 平行 `*_DEEP*` / `*_COMPLETE*` / `*_OVERVIEW*`。

---

## v0.15.0+ 模块拆分

| 模块 | 路径 | 约行数（2026-07） | 职责 |
|------|------|-------------------|------|
| `AIAgent` 壳 | `run_agent.py` | ~6680 | 构造、配置、转发 |
| **对话主循环** | `agent/conversation_loop.py` | ~5840 | `run_conversation()` |
| 上下文压缩 | `agent/context_compressor.py` | ~3740 | handoff、route pin |
| 流式 API | `agent/chat_completion_helpers.py` | ~3800 | reasoning/content delta |
| Prompt | `agent/prompt_builder.py` | ~1900 | system prompt |
| CLI | `hermes_cli/main.py` | ~15650 | 子命令 |
| TUI | `ui-tui/src/` | — | Ink + Widget SDK |
| 桥 | `tui_gateway/server.py` | ~16400 | WS、skin watcher |
| Desktop | `apps/desktop/` | — | Electron + SSH |
| 投递账本 | `gateway/delivery_ledger.py` | ~340 | 最终回复义务 |

```text
run_agent.AIAgent.run_conversation  →  conversation_loop.run_conversation
chat_completion_helpers             →  _fire_reasoning_delta / _fire_stream_delta
tui_gateway._agent_cbs              →  reasoning.delta | thinking.delta
ui-tui turnController               →  recordReasoningDelta → msg.thinking
hermes_cli.route_identity           →  should_clear_context_pin
kanban_db.repair_db                 →  hermes kanban repair
```

---

## Memory 叙事

只用三层：Persistent Memory · Session Search · Optional External Provider。  
「六层」= 扩展分析视角，不是主 API。见 `MEMORY_SYSTEM.md` §1 / 附录 A。  
2026-07-31 已对合并 Parts 去重重构为扁平 §1–§11。

---

## 刷新检查清单

- [ ] 文首 `0.19.x` + 核对日期
- [ ] 新 Surface 行为 → 只改 `SURFACE_ARCHITECTURE.md`
- [ ] 新循环/压缩行为 → `AGENT_LOOP_ARCHITECTURE.md` §10
- [ ] 新 IM/投递/CLI 启动行为 → `CLI_GATEWAY_SYSTEM.md`
- [ ] Memory / Tools / Prompt / 多 Agent → 对应单一 Canonical
- [ ] 发版能力 → `VERSION_HISTORY.md`
- [ ] 更新本文件行数表（`wc -l`）
- [ ] 英文 `website/docs/` 是否需同步（用户向）

---

## 相关

- [README.md](README.md)
- [VERSION_HISTORY.md](VERSION_HISTORY.md)
- [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md)
