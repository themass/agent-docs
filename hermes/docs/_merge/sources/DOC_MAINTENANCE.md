# 文档维护基准（源码锚点）

> **工作区**: `hermes-dev/hermes-agent/` · `__release_date__` **2026.9.24**  
> **核对日期**: 2026-10-14  
> **分类目录**: [CATALOG.md](CATALOG.md)

---

## Canonical 地图（按 CATALOG 类）

| 类 | Canonical | 新结论写哪里 |
|----|-----------|--------------|
| B | `ARCHITECTURE.md` | §0 / §4 / §11 |
| C | `SURFACE_ARCHITECTURE.md` | 全文 |
| D | `AGENT_LOOP_ARCHITECTURE.md` · `STATE_AND_AUXILIARY.md` | 循环 vs SessionDB/auxiliary |
| E | `PROMPT_SYSTEM_ARCHITECTURE.md` | §1–§17 |
| F | `MEMORY_*` · `TOOLS_*` · `SKILLS_*` · `MCP_*` · `PLUGINS_*` | 各单文件 |
| G | `CLI_GATEWAY_SYSTEM.md` · `HITL_APPROVAL_FLOW.md` | §4 网关；附录不写新结论 |
| H | `MULTI_AGENT_ARCHITECTURE.md` | §1–§16；Kanban 深潜单独 `KANBAN_*` |
| I | `SECURITY_SCAN_DEEP_ANALYSIS.md` | Part A 安全 · Part B Background Review |
| A | `VERSION_HISTORY.md` | 发版表 |

### 2026-10-14 整理

| 动作 | 说明 |
|------|------|
| `EXECUTION_FLOW` | → `archive/`；stub 在根目录 |
| `BACKGROUND_REVIEW` | → `SECURITY` Part B |
| `CLI_GATEWAY` 文末重复 | → `appendices/GATEWAY_RUNNER_WALKTHROUGH.md`（摘要） |
| 新增 | `CATALOG.md` · `STATE_AND_AUXILIARY.md` |

勿再 fork `*_DEEP*` / `*_COMPLETE*` / `*_OVERVIEW*`。

---

## 模块规模（2026-10 `wc -l` 快照）

| 模块 | 路径 | 约行数 |
|------|------|--------|
| `AIAgent` 壳 | `run_agent.py` | ~1550 |
| **对话主循环** | `agent/conversation_loop.py` | ~1860 |
| SessionDB 包 | `hermes_state*.py`（34 文件） | 见 STATE_AND_AUXILIARY |
| Auxiliary | `agent/auxiliary_*.py` | ~17 文件 |
| CLI | `hermes_cli/` | 500+ 模块文件 |
| TUI 桥 | `tui_gateway/` | ~86 py |
| 投递账本 | `gateway/delivery_ledger.py` | ~340 |

```text
run_agent.AIAgent.run_conversation  →  conversation_loop.run_conversation
publish_session_event（AgentScope）≠ Hermes；Hermes 用 SessionDB + gateway delivery
```

---

## Memory 叙事

主模型仍为 **三层**：Persistent Memory · Session Search · Optional External Provider。  
「六层」= AGENT_LOOP 扩展分析视角。见 `MEMORY_SYSTEM.md` §1。

---

## 刷新检查清单

- [ ] 文首版本 + 核对日期
- [ ] 新 Surface → `SURFACE_ARCHITECTURE.md`
- [ ] 新循环/SessionDB → `AGENT_LOOP` + `STATE_AND_AUXILIARY`
- [ ] 新 IM/投递 → `CLI_GATEWAY` §4
- [ ] 发版 → `VERSION_HISTORY.md`
- [ ] 更新本表行数（`wc -l`）
- [ ] `website/docs/` 英文是否需同步

---

## 相关

- [README.md](README.md)
- [CATALOG.md](CATALOG.md)
