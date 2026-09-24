# Codex — 架构导航

> **完整大纲**: [README.md](./README.md) · **源码根**: `codex/codex-rs/`

---

## 分章索引

| 主题 | 文档 | 章节 |
|------|------|------|
| 核心运行时 | [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | Thread/Session/Turn、SQ/EQ、Agent Loop、Message、E2E、Context、多 Agent、Plan |
| 扩展与安全 | [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | Tool、MCP、Skills、Sandbox、crate 地图 |
| **安全导读（图表）** | [SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md) | 四层防御、审批/Guardian、Hook |
| **多 Agent 导读（V1/V2）** | [MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md) | notification vs 邮箱、trigger_turn |
| 持久化与取舍 | [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | Rollout、Hooks、Observability、优缺点 |

## 专题深潜

| 主题 | 文档 |
|------|------|
| **实体 ER + 端到端/模块时序（源码级）** | [**ENTITY_AND_SEQUENCES.md**](./ENTITY_AND_SEQUENCES.md) |
| **安全：四层防御 + Hook + Guardian** | [**SECURITY_ARCHITECTURE.md**](./SECURITY_ARCHITECTURE.md) |
| **多 Agent：MA V1/V2** | [**MULTI_AGENT_ARCHITECTURE.md**](./MULTI_AGENT_ARCHITECTURE.md) |
| 冷启动 / 第二问 / Resume / 压缩实例 | [CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md) |

## 10 分钟速览

1. **一 Thread 一 Session**，Session 同时最多一个 `ActiveTurn` → [PART1 §2](./ARCHITECTURE_PART1.md#第2章身份模型thread--session--turn--step)
2. 客户端只走 **SQ/EQ**：`Op` 进、`EventMsg` 出 → [PART1 §3](./ARCHITECTURE_PART1.md#第3章sqeq-协议)
3. 一轮用户问题 = `run_turn()`：compact → fragments → 采样 → 工具 → 再采样 → [PART1 §4](./ARCHITECTURE_PART1.md#第4章agent-looprun_turn)
4. 模型看见的是 `ResponseItem[]`，UI 看见的是 `EventMsg` / `TurnItem`，两套投影 → [PART1 §5](./ARCHITECTURE_PART1.md#第5章message-设计三层投影)
5. 历史 **只追加不改写**；压缩换窗口，不原地 mutilate → [PART1 §7](./ARCHITECTURE_PART1.md#第7章context-fragments-与压缩)
6. Plan **不是** `update_plan` 工具；那是 TODO checklist。Plan 是 `ModeKind::Plan` collaboration mode → [PART1 §9](./ARCHITECTURE_PART1.md#第9章plan-与-collaboration-mode)
7. 子 Agent 是 **新 Thread**（`spawn_agent`），用 `InterAgentCommunication` 回灌 → [PART1 §8](./ARCHITECTURE_PART1.md#第8章多-agent)

## 设计目标（一句话）

把「本地编码 Agent」做成一个 **可被多种前端复用的协议运行时**：上下文可缓存、历史可回放、工具可审批、沙箱可升级、多 Agent 可隔离。

返回：[文档中心](./README.md)
