# 跨项目 Agent 设计导读索引

> **目标**：用 **循序渐进的设计思想导读**，先建立可运转的心智模型，再跳进各项目 `ARCHITECTURE` 深潜。  
> **写法标准**：[agent-doc-template/PROGRESSIVE_ARCH_DOC_METHODOLOGY.md](./agent-doc-template/PROGRESSIVE_ARCH_DOC_METHODOLOGY.md)  
> **原则**：只增导读文档，不删改现有 `ARCHITECTURE*.md`。

---

## 这种文档好在哪里

不是「章节多」，而是：

1. **按一次运行的时间顺序讲**，不是按包名列目录  
2. **每节一个概念** + 一句话 + 图/表 + 源码锚点  
3. **先 WHY 再 HOW**，并写清易错点与校正  
4. **三层分工**：导读（30min）→ Part I（图表权威）→ Part II（改代码）

Pi 图解系列是这种写法的标杆；本仓库用 `DESIGN_THINKING_SERIES.md` 承载同类内容，章节数随项目伸缩。

---

## 常见认知阶梯（跨项目对照用）

| 阶梯 | 要回答的问题 |
|------|--------------|
| 源码地图 | 仓库里谁是谁？ |
| 状态 vs 执行 | 谁管生命周期、谁管单轮循环？ |
| 循环结构 | 外层会话与内层 turn+tool 如何分？ |
| 装配依赖 | CLI/RPC 如何接到 core？ |
| 工具管线 | 为何不是 model 直接 execute？ |
| 事件投影 | UI、模型、磁盘各看到什么？ |
| 中途输入 | steer / follow-up / interrupt 语义？ |
| 持久化账本 | 几本账、JSONL/rollout 树？ |
| 核心与边界 | 什么进 core、什么进扩展？ |

概念对照表：[agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md](./agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md)

---

## 项目矩阵

| 项目 | 循序渐进导读 | 深潜入口 | Archify 图解 | 树形 / 账本专题 |
|------|--------------|----------|-----------------|
| **Pi** | [九幕导读](./pi-agent/DESIGN_THINKING_SERIES.md) · [HTML 图解](./pi-agent/diagrams/design-thinking-series.html) · [GUIDE §三](./prime-agent-architecture/ARCHITECTURE_GUIDE.md#三与-pi-的整体关系) | [**pi-architecture/**](./pi-architecture/README.md) · [pi-agent/ARCHITECTURE](./pi-agent/ARCHITECTURE.md) | [PI 栈图](./pi-architecture/PI_STACK_ARCHITECTURE.md) · [Prime diagrams](./prime-agent-architecture/diagrams/README.md) | [pi-agent/JSONL](./pi-agent/JSONL_TREE_GUIDE.md) |
| **Codex** | [DESIGN_THINKING_SERIES.md](./codex-architecture/DESIGN_THINKING_SERIES.md) | [README.md](./codex-architecture/README.md) | [diagrams/](./codex-architecture/diagrams/README.md) | [JSONL_TREE_GUIDE.md](./codex-architecture/JSONL_TREE_GUIDE.md) |
| **Prime Agent** | [**ARCHITECTURE_GUIDE**](./prime-agent-architecture/ARCHITECTURE_GUIDE.md) · [EXTERNAL_ARTICLES](./prime-agent-architecture/EXTERNAL_ARTICLES_SYNTHESIS.md) | [ARCHITECTURE_REFERENCE](./prime-agent-architecture/ARCHITECTURE_REFERENCE.md) | [**diagrams/**](./prime-agent-architecture/diagrams/README.md)（10 张） | [_archive/ENTITY](./prime-agent-architecture/_archive/ENTITY_AND_SEQUENCES.md) |
| **DeepTutor** | [DESIGN_THINKING_SERIES.md](./deeptutor-architecture/DESIGN_THINKING_SERIES.md) · [CONTEXT_AND_PROJECTION.md](./deeptutor-architecture/CONTEXT_AND_PROJECTION.md) | [ARCHITECTURE.md](./deeptutor-architecture/ARCHITECTURE.md) | [diagrams/](./deeptutor-architecture/diagrams/README.md) | [ENTITY_AND_SEQUENCES.md](./deeptutor-architecture/ENTITY_AND_SEQUENCES.md) |
| **Grok Build** | [DESIGN_THINKING_SERIES.md](../grok-build/doc-cn/DESIGN_THINKING_SERIES.md) | [grok-build-architecture/](./grok-build-architecture/README.md) | [diagrams/](./grok-build-architecture/diagrams/README.md) | 与 Pi 对照 §II.4 |
| **Agent Framework** | [DESIGN_THINKING_SERIES.md](../agent-framework/docs/DESIGN_THINKING_SERIES.md) | [agent-framework-architecture/](./agent-framework-architecture/README.md) | [diagrams/](./agent-framework-architecture/diagrams/README.md) | ADR + samples |
| **OpenAI Agents SDK** | [DESIGN_THINKING_SERIES.md](../openai-agents-python/docs/DESIGN_THINKING_SERIES.md) | [openai-agents-architecture/](./openai-agents-architecture/README.md) | [diagrams/](./openai-agents-architecture/diagrams/README.md) | [ROLLOUT_AND_SESSION_EXAMPLES.md](../openai-agents-python/docs/ROLLOUT_AND_SESSION_EXAMPLES.md) |
| **OpenHuman** | [DESIGN_THINKING_SERIES.md](../openhuman/doc-cn/DESIGN_THINKING_SERIES.md) · [图解 HTML](../openhuman/doc-cn/diagrams/design-thinking-series.html) | [ARCHITECTURE.md](../openhuman/doc-cn/ARCHITECTURE.md) | [JSONL_TRANSCRIPT_GUIDE.md](../openhuman/doc-cn/JSONL_TRANSCRIPT_GUIDE.md) |
| **Harness 横向对比** | [00-HARNESS-DESIGN-PHILOSOPHY.md](../OpenHarness/docs/framework-comparison/00-HARNESS-DESIGN-PHILOSOPHY.md) · [HARNESS-SPECTRUM.md](../OpenHarness/docs/framework-comparison/HARNESS-SPECTRUM.md) | [framework-comparison/README.md](../OpenHarness/docs/framework-comparison/README.md) | [21-session-message-architecture.md](../OpenHarness/docs/framework-comparison/21-session-message-architecture.md) |
| **OpenCode** | [README](./opencode-architecture/README.md) · [AGENT_AND_MULTI_AGENT](./opencode-architecture/AGENT_AND_MULTI_AGENT.md) | [ARCHITECTURE](./opencode-architecture/ARCHITECTURE.md)（§0–§16 主 spine + 存档分卷） | [diagrams/](./opencode-architecture/diagrams/README.md) | [opencode/CONTEXT.md](../opencode/CONTEXT.md) |
| **Hindsight** | [DESIGN_THINKING](./hindsight-architecture/DESIGN_THINKING_SERIES.md) · [同类项目表](./hindsight-architecture/MEMORY_LANDSCAPE.md) | [**ARCHITECTURE_GUIDE**](./hindsight-architecture/ARCHITECTURE_GUIDE.md) · [MEMORY_LANDSCAPE](./hindsight-architecture/MEMORY_LANDSCAPE.md) · [INTEGRATIONS](./hindsight-architecture/INTEGRATIONS.md) | 文内 mermaid + 选型流程图 | [hindsight/CLAUDE.md](../hindsight/CLAUDE.md) · 记忆服务（无 agent loop） |
| **TencentDB Agent Memory** | [TENCENTDB 解读](./hindsight-architecture/TENCENTDB_AGENT_MEMORY.md) · [MEMORY_LANDSCAPE 行](./hindsight-architecture/MEMORY_LANDSCAPE.md) | 插件 L0–L3 + Mermaid 卸载；v2 Memory Hub（Chat Memory / Skill / Wiki / CodeGraph）+ Proxy | 文内部署/序列图 | 外部仓库 [TencentCloud/TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) · 横切记忆层 |
| **OpenManus** | [DESIGN_THINKING_SERIES](./openmanus-architecture/DESIGN_THINKING_SERIES.md) · [**Plan 模式源码导读**](./openmanus-architecture/PLAN_MODE_SOURCE_WALKTHROUGH.md) | [PART1](./openmanus-architecture/ARCHITECTURE_PART1.md) · [ATLAS](./openmanus-architecture/ARCHITECTURE_ATLAS.md) | [diagrams/](./openmanus-architecture/diagrams/README.md) | [ARCHITECTURE_DESIGN.md](../OpenManus/docs/ARCHITECTURE_DESIGN.md) |
| **MetaGPT** | [**ARCHITECTURE**](./metagpt-architecture/ARCHITECTURE.md)（主文档 ~2.7k 行）；专题 [类图与运行时](./metagpt-architecture/CLASS_DIAGRAM_AND_RUNTIME.md)、[§18.4/18.5 外部与认知模块](./metagpt-architecture/EXTERNAL_AND_COGNITIVE_MODULES.md)、[Plan + Message + Loop](./metagpt-architecture/PLAN_MODE.md)、[Hook/扩展点](./metagpt-architecture/HOOKS_AND_EXTENSION_POINTS.md)、[ReAct/WritePRD](./metagpt-architecture/REACT_THINK_ACT_AND_WRITEPRD.md)、[角色 Prompt 中文](./metagpt-architecture/ROLE_PROMPTS_ZH.md)、[TeamLeader 端到端](./metagpt-architecture/TEAMLEADER_E2E_SOFTWARE_COMPANY.md) | 同上（正文含 ATLAS 分卷） | [diagrams/](./metagpt-architecture/diagrams/README.md) | 官方 [docs.deepwisdom.ai](https://docs.deepwisdom.ai/main/en/) |
| **crewAI** | [crewai-architecture/](./crewai-architecture/README.md) | [crewAI/](../crewAI/) | [diagrams/](./crewai-architecture/diagrams/README.md) | [AGENT_PROJECTS 对比](./AGENT_PROJECTS_FULL_ARCHITECTURE_COMPARISON.md) |
| **Hermes Agent** | [FEATURE_DESIGN_CATALOG](./hermes-agent-architecture/FEATURE_DESIGN_CATALOG.md) · [Workspace CHANGELOG](../hermes-dev/hermes-workspace/CHANGELOG.md) | [hermes-agent-architecture/](./hermes-agent-architecture/README.md) | 待建 Archify | [MULTI_AGENT_ARCHITECTURE](../hermes-dev/hermes-agent/docs/MULTI_AGENT_ARCHITECTURE.md) · [Swarm2 spec](../hermes-dev/hermes-workspace/docs/swarm2-agent-ide-spec.md) |
| **Codewhale** | [DESIGN_THINKING_SERIES](./codewhale-architecture/DESIGN_THINKING_SERIES.md) | [codewhale-architecture/](./codewhale-architecture/README.md) | 文内 mermaid（Part 1–2） | 上游 [`Codewhale/docs/ARCHITECTURE.md`](../Codewhale/docs/ARCHITECTURE.md) · [`AGENT_RUNTIME.md`](../Codewhale/docs/AGENT_RUNTIME.md) |
| **Harness-SDK（Python）** | [DESIGN_THINKING_SERIES](./harness-sdk-architecture/DESIGN_THINKING_SERIES.md) | [harness-sdk-architecture/](./harness-sdk-architecture/README.md) | 文内 mermaid（Part 1–2） | `create_harness` + `event_loop_cycle`；对照 [maf-agent](./maf-agent/docs/README.md) |
| **SoL-Pi** | [DESIGN_THINKING_SERIES](./sol-pi-architecture/DESIGN_THINKING_SERIES.md) | [sol-pi-architecture/](./sol-pi-architecture/README.md) | 文内 mermaid（Part 1–2） | Pi 扩展；先读 [pi-architecture](./pi-architecture/README.md) |
| **Understand-Anything** | [DESIGN_THINKING_SERIES](./understand-anything-architecture/DESIGN_THINKING_SERIES.md) | [understand-anything-architecture/](./understand-anything-architecture/README.md) | 文内 mermaid（Part 1–2） | 知识图谱插件；非 agent loop |
| **四项目对照** | [FOUR_PROJECT_ARCHITECTURE_INDEX](./FOUR_PROJECT_ARCHITECTURE_INDEX.md) | 各项目 **ARCHITECTURE_GUIDE** + **MODULE_CATALOG** | 对照流程图 | 谁拥有 loop / Session / Memory / 权限 |

---

## 推荐阅读顺序

```text
PROGRESSIVE_ARCH_DOC_METHODOLOGY（理解写法，可选）
    → 项目 DESIGN_THINKING_SERIES（建立心智模型；Codex/OpenHuman/Pi ~40min）
    → ARCHITECTURE Part I（图表与实体，~20min）
    → JSONL / ENTITY 树形导读（持久化专题）
    → Part II / RUNTIME_PROMPTS / IMPLEMENTATION（改代码时）
```

---

## 外部参考

- [Pi 设计思想图解系列](https://mp.weixin.qq.com/s/WB24MCub0fosrhZOlEiSAQ)（微信公众号 · AI秘境；本仓库以源码为准）
