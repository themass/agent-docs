# Agent 研究与拆解（agent-research）

> **定位**：本 monorepo 的 **Agent 技术研究与源码学习索引**，不替代各子项目的官方文档。  
> **最后更新**：2026-07-27

---

## 本目录是什么？

`agent-research/` **不是**某个叫 `agent-research` 的 Agent 产品（OpenHarness 文档里的 `agent-research-beijing` 只是 swarm 示例 ID）。

这里是 **研究笔记与导航**：

| 文档 | 内容 |
|------|------|
| [**SAYAGAIN.md**](./SAYAGAIN.md) | **SayAgain 英语跟读纠错** — 唯一产品文档（PRD + 设计 + API + 技术） |
| [**english-shadowing/**](./english-shadowing/) | Phase 0 代码：对齐 + 及格规则 + 双语教练 |
| [**HER_COMPANION_PRODUCT_BRIEF.md**](./HER_COMPANION_PRODUCT_BRIEF.md) | **Her 式语音伴侣** — 愿景、需求基线、路线图（PRD 0.1） |
| [**her-companion/**](./her-companion/) | **Phase 0 样机** — LiveKit 语音 + Hermes 记忆 + 小棠 persona |
| [**OSS_AGENT_RESEARCH_CATALOG.md**](./OSS_AGENT_RESEARCH_CATALOG.md) | monorepo 内 + 仓外值得源码级学习的 Agent 项目清单与分层 |
| [**CLAUDE_CODE_MASTER_ARCHITECTURE.md**](./CLAUDE_CODE_MASTER_ARCHITECTURE.md) | **合并** `claude-code/`（官方插件层）+ `claude-code-agent/`（运行时快照）+ SDK 的源码级设计总册 |
| [**CLAUDE_CODE_LEARNING_PATH.md**](./CLAUDE_CODE_LEARNING_PATH.md) | Claude Code 按周阅读路线与习题 |

---

## 与本 monorepo 其他文档的关系

```text
agent-research/                    ← 你在这里（研究入口）
├── CLAUDE_CODE_MASTER_ARCHITECTURE.md
OpenHarness/docs/framework-comparison/   ← 多框架横向对比（Tier 1/2）
claude-code/docs/                        ← 官方 clone：插件/Hook/CHANGELOG
claude-code-agent/docs/architecture/     ← 运行时快照 18 篇深潜
claude-agent-sdk-python/docs/            ← Python 控制面 / stream-json
```

**读 Claude Code 建议顺序**：

1. [CLAUDE_CODE_MASTER_ARCHITECTURE.md](./CLAUDE_CODE_MASTER_ARCHITECTURE.md) §0–§2（两仓关系 + 三层产品）  
2. `claude-code-agent/docs/architecture/00-overview.md`  
3. `01-agent-loop-core.md` → `03` → `06` → `07` → `15`  
4. `claude-code/docs/CLAUDE_CODE_ARCHITECTURE_GUIDE.md`（扩展面与插件地图）  
5. 对照 `claude-code/plugins/plugin-dev/` 动手写 Hook/Skill

---

## 快速链接

| 路径 | 说明 |
|------|------|
| `../claude-code/` | Anthropic 官方仓库 clone（plugins、examples、CHANGELOG） |
| `../claude-code-agent/` | 2026-03-31 公开快照 + `src/` + 架构 18 篇 |
| `../claude-agent-sdk-python/` | Python SDK（spawn CLI） |
| `../OpenHarness/docs/framework-comparison/` | Hermes / deer-flow / OpenHands 等对比 |
| `../github-daily-rank/2026/07/GITHUB_2026_07_REPORT.md` | 2026 年 7 月 GitHub 日榜 Agent 热点 |

---

**维护**：新增值得研究的仓或 Claude Code 大版本时，更新 Catalog 与 Master Architecture 的「版本钉扎」节。
