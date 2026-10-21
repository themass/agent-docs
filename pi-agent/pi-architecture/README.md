# Pi 架构与设计思想 · 文档入口

> **版本核验：2026-10-17 / Pi v1.3.0**。本目录当前源码结论固定到官方 tag `71023aec1546d6d677a65669c5665c0927ce0dd0`。旧文中的 `agent/src/harness/`、Lane/registers、`LeafEntry` 和 Prime/第三方生态不能视为 v1.3.0 的 core 实现；具体差异见 [版本核验与纠错](../VERSION_ALIGNMENT.md)。历史示例保留并就地标记，旧行号不作为当前定位依据。


> **源码**：仓库根目录 [官方 v1.3.0 源码](https://github.com/earendil-works/pi/tree/v1.3.0)（`pi-agent-core` / `pi-coding-agent` / `pi-ai`）
> **本 monorepo 的中文整理**在 **`docs/pi-agent/`**；**Prime 产品封装**在 **`docs/prime-agent-architecture/`**。  
> 若你从 CROSS_AGENT_DESIGN_INDEX（历史引用：`../CROSS_AGENT_DESIGN_INDEX.md`，当前文件不存在） 点进来，这里是对 Pi 行的统一导航。

---

## 1. 设计思想（九幕 · 图解）

对应微信公众号「Pi 设计思想」系列；**当前以官方 v1.3.0 发布源码为准；原交互图解为历史导读**。

| 形式 | 路径 | 说明 |
|------|------|------|
| **文字导读** | [pi-agent/DESIGN_THINKING_SERIES.md](../DESIGN_THINKING_SERIES.md) | 九幕循序渐进，约 30 分钟 |
| **蓝白交互页** | [pi-agent/diagrams/design-thinking-series.html](../diagrams/design-thinking-series.html) | 浏览器打开，与九幕同结构 |
| 外部原文 | [Pi 设计思想图解](https://mp.weixin.qq.com/s/WB24MCub0fosrhZOlEiSAQ) | 公众号；细节以源码校正 |

---

## 2. 架构深潜（Pi 本体）

当前 v1.3.0 发布源码的全景和后端补充：

- [V1.3-durable 统一设计文档](../V1.3-durable.md)（推荐主入口：pi-agent + pi-durable + 设计思考）
- [PI_SOURCE_DEEP_DIVE_2026](../PI_SOURCE_DEEP_DIVE_2026.md)
- [BACKEND_RUNTIME](../BACKEND_RUNTIME.md)
- [SOURCE_MAP](../SOURCE_MAP.md)


| 文档 | 路径 |
|------|------|
| 文档中心 | [pi-agent/README.md](../README.md) |
| Part I/II 综合专题（含历史示例） | [pi-agent/ARCHITECTURE.md](../ARCHITECTURE.md) |
| JSONL 会话树 | [pi-agent/JSONL_TREE_GUIDE.md](../JSONL_TREE_GUIDE.md) |
| 扩展 / Skills / Prompt | [EXTENSIONS](../EXTENSIONS.md) · [SKILLS](../SKILLS_LIFECYCLE.md) · [RUNTIME_PROMPT](../RUNTIME_PROMPT.md) |

[本目录综合架构](../ARCHITECTURE.md) 是本地中文整理，不是官方 v1.3.0 自带的英文长文；本地 `pi/docs/` 中自行加入的文档也不能作为上游发布证据。

---

## 3. 架构图（Archify · 可交互 HTML）

### Pi 栈 + Prime 封装（分层总览）

| 图 / 文 | 路径 |
|---------|------|
| **Pi 栈全图（L0–L4 + 🟧 Prime）** | [PI_STACK_ARCHITECTURE.md](./PI_STACK_ARCHITECTURE.md) |
| Pi 与 Prime 关系说明 | [prime-agent-architecture/_archive/PI_AND_PRIME.md](../../prime-agent-architecture/_archive/PI_AND_PRIME.md) |
| 主指南 §三（合并版） | [ARCHITECTURE_GUIDE §三](../../prime-agent-architecture/ARCHITECTURE_GUIDE.md#三与-pi-的整体关系) |

### Prime 产品图解（含双环、JSONL、steer、RLM 等）

完整 10 张：[prime-agent-architecture/diagrams/README.md](../../prime-agent-architecture/diagrams/README.md)

| 图 | 说明 |
|----|------|
| [stack](../../prime-agent-architecture/diagrams/prime-agent-stack.html) | 架构总览 |
| [dual-loop](../../prime-agent-architecture/diagrams/prime-agent-dual-loop.html) | 双环 Loop |
| [steer](../../prime-agent-architecture/diagrams/prime-agent-steer.html) | steer / follow-up |
| [jsonl](../../prime-agent-architecture/diagrams/prime-agent-jsonl.html) | JSONL 数据流 |
| [e2e](../../prime-agent-architecture/diagrams/prime-agent-e2e.html) | 端到端时序 |

### 与其它 Agent 对照

| 图 | 路径 |
|----|------|
| Grok Build ↔ Pi | [grok-build-architecture/diagrams/grok-build-pi-comparison.architecture.html](../../grok-build-architecture/diagrams/grok-build-pi-comparison.architecture.html) |

---

## 4. 推荐阅读顺序

```text
DESIGN_THINKING_SERIES（或 design-thinking-series.html）
    → pi-agent/JSONL_TREE_GUIDE
    → pi-agent/ARCHITECTURE Part I
    → PI_STACK_ARCHITECTURE + Prime diagrams（若做 Prime 产品）
    → pi-agent/ARCHITECTURE Part II（改代码）
```

跨项目索引：CROSS_AGENT_DESIGN_INDEX（历史引用：`../CROSS_AGENT_DESIGN_INDEX.md`，当前文件不存在） · 概念表：CROSS_AGENT_CONCEPT_MAP（历史引用：`../agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md`，当前文件不存在）

---

**维护**：Deep Agents Team · 若链接失效，优先查 `docs/pi-agent/` 是否在本机未 `git add`（设计思想系列与 `diagrams/` 曾为未跟踪文件）。

## 目录迁移后的正确入口（原导航保留）

- [Pi 源码](../../../pi/)
- [文档中心](../README.md)
- [设计思想](../DESIGN_THINKING_SERIES.md)
- [会话树](../JSONL_TREE_GUIDE.md)
- [架构深潜](../ARCHITECTURE.md)
- [运行时服务](../RUNTIME_SERVICES.md)
- [覆盖审计与改动摘要](../COVERAGE_AND_CHANGES.md)
