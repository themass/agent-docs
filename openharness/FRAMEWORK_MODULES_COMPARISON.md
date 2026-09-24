# Harness / Agent 模块横向对比（入口）

> **定位**：OpenHarness 文档体系中 **全工程 Agent 框架对比** 的轻量入口。  
> **真源目录**：[`framework-comparison/`](./framework-comparison/README.md)（扁平 **01–14** 编号专题）。  
> **最后更新**：2026-08-05（恢复 `_archive` 长文至 12/13）

---

## 怎么读

| 阶段 | 文档 | 时间 |
|------|------|------|
| 快速选型 | [01-overview.md](./framework-comparison/01-overview.md) §2 清单 · §4 矩阵 · §15 决策树 | ~1h |
| 自建 Harness | [02-harness-blueprint.md](./framework-comparison/02-harness-blueprint.md) → [06-memory](./framework-comparison/06-memory.md) → [07-compression](./framework-comparison/07-compression.md) | ~3h |
| 模块级长论证 | [12-modules-reference.md](./framework-comparison/12-modules-reference.md)（Memory/Prompt/Harness/安全 §1–§11） | 按需 |
| 压缩源码 walkthrough | [13-compression-source-archive.md](./framework-comparison/13-compression-source-archive.md) | 按需 |

完整大纲与阅读顺序见 [**framework-comparison/README.md**](./framework-comparison/README.md)。

---

## 编号专题一览

| 编号 | 文档 | 类别 |
|------|------|------|
| 01 | [01-overview.md](./framework-comparison/01-overview.md) | 总览 · 选型 |
| 02 | [02-harness-blueprint.md](./framework-comparison/02-harness-blueprint.md) | Harness 蓝图 |
| 03 | [03-runtime-loop-queue.md](./framework-comparison/03-runtime-loop-queue.md) | 运行时 · 队列 |
| 04 | [04-multi-agent.md](./framework-comparison/04-multi-agent.md) | 多 Agent |
| 05 | [05-plan-mode.md](./framework-comparison/05-plan-mode.md) | Plan / Todo / Grok |
| 06 | [06-memory.md](./framework-comparison/06-memory.md) | Memory 横向 + 深潜 |
| 07 | [07-compression.md](./framework-comparison/07-compression.md) | 压缩矩阵 + 深潜 |
| 08 | [08-mcp.md](./framework-comparison/08-mcp.md) | MCP |
| 09 | [09-channels.md](./framework-comparison/09-channels.md) | 渠道 |
| 10 | [10-openhands.md](./framework-comparison/10-openhands.md) | OpenHands |
| 11 | [11-product-deep-dives.md](./framework-comparison/11-product-deep-dives.md) | Claude SDK · nanobot 等 |
| **12** | [12-modules-reference.md](./framework-comparison/12-modules-reference.md) | **模块深度参考**（恢复单体） |
| **13** | [13-compression-source-archive.md](./framework-comparison/13-compression-source-archive.md) | **压缩源码归档**（恢复） |
| **14** | [14-loop-interjection.md](./framework-comparison/14-loop-interjection.md) | **Loop 插队**（inject / steer / interjection） |

---

## 与旧文件名对照

| 旧路径 | 现行文档 |
|--------|----------|
| `INDEX.md` | [framework-comparison/README.md](./framework-comparison/README.md) |
| `AGENT_FRAMEWORK_IMPLEMENTATION_COMPARISON.md` | [01-overview.md](./framework-comparison/01-overview.md) |
| `00_OVERVIEW.md` / `MATRIX_OVERVIEW` | [01-overview.md](./framework-comparison/01-overview.md) 后半 |
| `memory_*_DEEP_DIVE.md` | [06-memory.md](./framework-comparison/06-memory.md) 深潜章节 |
| `CONTEXT_COMPRESSION_*` 长文 | [07-compression.md](./framework-comparison/07-compression.md) + [13-compression-source-archive.md](./framework-comparison/13-compression-source-archive.md) |
| `_archive/FRAMEWORK_MODULES_MONOLITH_V3.md` | [12-modules-reference.md](./framework-comparison/12-modules-reference.md) |
| `PLAN_MODE_IMPLEMENTATION_COMPARISON.md` | [05-plan-mode.md](./framework-comparison/05-plan-mode.md) |

---

## 关联教程

- MCP Agent 使用：[MCP_AGENT_AND_TOOLS.md](./MCP_AGENT_AND_TOOLS.md)
- OpenHarness 架构索引：[README.md](./README.md)
