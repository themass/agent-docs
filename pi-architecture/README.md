# Pi 架构与设计思想 · 文档入口

> **源码**：仓库根目录 [`pi/`](../../pi/)（`pi-agent-core` / `pi-coding-agent` / `pi-ai`）  
> **本 monorepo 的中文整理**在 **`docs/pi-agent/`**；**Prime 产品封装**在 **`docs/prime-agent-architecture/`**。  
> 若你从 [CROSS_AGENT_DESIGN_INDEX](../CROSS_AGENT_DESIGN_INDEX.md) 点进来，这里是对 Pi 行的统一导航。

---

## 1. 设计思想（九幕 · 图解）

对应微信公众号「Pi 设计思想」系列；**以本仓库 `pi/` 源码为准**。

| 形式 | 路径 | 说明 |
|------|------|------|
| **文字导读** | [pi-agent/DESIGN_THINKING_SERIES.md](../pi-agent/DESIGN_THINKING_SERIES.md) | 九幕循序渐进，约 30 分钟 |
| **蓝白交互页** | [pi-agent/diagrams/design-thinking-series.html](../pi-agent/diagrams/design-thinking-series.html) | 浏览器打开，与九幕同结构 |
| 外部原文 | [Pi 设计思想图解](https://mp.weixin.qq.com/s/WB24MCub0fosrhZOlEiSAQ) | 公众号；细节以源码校正 |

---

## 2. 架构深潜（Pi 本体）

| 文档 | 路径 |
|------|------|
| 文档中心 | [pi-agent/README.md](../pi-agent/README.md) |
| Part I/II 权威 | [pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md) |
| JSONL 会话树 | [pi-agent/JSONL_TREE_GUIDE.md](../pi-agent/JSONL_TREE_GUIDE.md) |
| 扩展 / Skills / Prompt | [EXTENSIONS](../pi-agent/EXTENSIONS.md) · [SKILLS](../pi-agent/SKILLS_LIFECYCLE.md) · [RUNTIME_PROMPT](../pi-agent/RUNTIME_PROMPT.md) |

`pi/docs/` 下另有上游英文长文 [ARCHITECTURE.md](../../pi/docs/ARCHITECTURE.md)，与 `docs/pi-agent/ARCHITECTURE.md` 同源整理，**九幕导读与 HTML 图解仅在 `docs/pi-agent/`**。

---

## 3. 架构图（Archify · 可交互 HTML）

### Pi 栈 + Prime 封装（分层总览）

| 图 / 文 | 路径 |
|---------|------|
| **Pi 栈全图（L0–L4 + 🟧 Prime）** | [PI_STACK_ARCHITECTURE.md](./PI_STACK_ARCHITECTURE.md) |
| Pi 与 Prime 关系说明 | [prime-agent-architecture/_archive/PI_AND_PRIME.md](../prime-agent-architecture/_archive/PI_AND_PRIME.md) |
| 主指南 §三（合并版） | [ARCHITECTURE_GUIDE §三](../prime-agent-architecture/ARCHITECTURE_GUIDE.md#三与-pi-的整体关系) |

### Prime 产品图解（含双环、JSONL、steer、RLM 等）

完整 10 张：[prime-agent-architecture/diagrams/README.md](../prime-agent-architecture/diagrams/README.md)

| 图 | 说明 |
|----|------|
| [stack](../prime-agent-architecture/diagrams/prime-agent-stack.html) | 架构总览 |
| [dual-loop](../prime-agent-architecture/diagrams/prime-agent-dual-loop.html) | 双环 Loop |
| [steer](../prime-agent-architecture/diagrams/prime-agent-steer.html) | steer / follow-up |
| [jsonl](../prime-agent-architecture/diagrams/prime-agent-jsonl.html) | JSONL 数据流 |
| [e2e](../prime-agent-architecture/diagrams/prime-agent-e2e.html) | 端到端时序 |

### 与其它 Agent 对照

| 图 | 路径 |
|----|------|
| Grok Build ↔ Pi | [grok-build-architecture/diagrams/grok-build-pi-comparison.architecture.html](../grok-build-architecture/diagrams/grok-build-pi-comparison.architecture.html) |

---

## 4. 推荐阅读顺序

```text
DESIGN_THINKING_SERIES（或 design-thinking-series.html）
    → pi-agent/JSONL_TREE_GUIDE
    → pi-agent/ARCHITECTURE Part I
    → PI_STACK_ARCHITECTURE + Prime diagrams（若做 Prime 产品）
    → pi-agent/ARCHITECTURE Part II（改代码）
```

跨项目索引：[CROSS_AGENT_DESIGN_INDEX](../CROSS_AGENT_DESIGN_INDEX.md) · 概念表：[CROSS_AGENT_CONCEPT_MAP](../agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md)

---

**维护**：Deep Agents Team · 若链接失效，优先查 `docs/pi-agent/` 是否在本机未 `git add`（设计思想系列与 `diagrams/` 曾为未跟踪文件）。
