# PenguinHarness — 设计文档目录（doc-sn）

> 学习用中文文档。权威行为以官方 `packages/docs/content/`、包 README、测试为准。  
> **怎么读**：先读 **[00-顶层设计与实体边界](./00-顶层设计与实体边界.md)**（封装边界 + 顶层目标），再查词、再全景。  
> **写作标准**：[DOC_QUALITY.md](./DOC_QUALITY.md) — **禁止**再出「只有流程图、新词墙、看不出谁封装什么」。

---

## 推荐阅读顺序

```text
① 顶层与实体边界  00-顶层设计与实体边界.md   ←【先读】拥有/不拥有/类图/决策树
② 术语表          GLOSSARY.md
③ 项目介绍        01-项目介绍与设计思路.md
④ 总体架构        02-总体架构与端到端.md       ← 流程须写「谁写入」（见 DOC_QUALITY）
⑤ 子系统全景      03-子系统全景.md
⑥ 关键场景        04-关键场景详解.md
⑦ 机制 PART1–3    ARCHITECTURE_PART*.md
⑧ 源码附录        source/
```

**不要**套用 DSH 的 Cordis / Profile / Bundle / Inbox splice。  
**不要**一上来只扫时序图——没有实体表等于没读懂。

---

## 总目录

### 入门

| 序号 | 文档 | 内容 |
|------|------|------|
| **0** | **[00-顶层设计与实体边界.md](./00-顶层设计与实体边界.md)** | 设计目标/非目标、分层、**实体封装表**、类图、run 协作、决策树 |
| 0′ | [DOC_QUALITY.md](./DOC_QUALITY.md) | doc-sn 写作铁律（防再水） |
| 1 | [GLOSSARY.md](./GLOSSARY.md) | 术语 |
| 2 | [01-项目介绍与设计思路.md](./01-项目介绍与设计思路.md) | 定位与动机 |
| 3 | [02-总体架构与端到端.md](./02-总体架构与端到端.md) | 模块与 E2E |
| 4 | [03-子系统全景.md](./03-子系统全景.md) | 广度 |
| 5 | [04-关键场景详解.md](./04-关键场景详解.md) | 场景 |

### 机制与源码

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | **~2k 行**：三接口/Session/Engine/OmniMessage/Trace；实体边界+写入归属+源码 |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | **~1.2k 行**：Skills/Env/Model/Goal/Subagent/Compaction/ApproveFn |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | **~1.2k 行**：包地图、表面、PENGUIN_HOME、vs DSH/Pi |
| [source/](./source/README.md) | 源码走读 |

---

## 文档结构逻辑

```text
谁封装什么、顶层取舍     → 00 + DOC_QUALITY
查词                     → GLOSSARY
为什么做这个产品         → 01
块与调用链               → 02–04（须带写入归属）
机制深挖                 → PART*
代码                     → source
```

---

## 与官方 docs/

| | 官方 `packages/docs/` | `doc-sn/` |
|--|----------------------|----------|
| 用途 | 产品文档站 | 学习向；**00 强制实体边界** |
| 入口 | https://penguin.ooo/docs/ | 本目录 |

改产品行为前仍以官方文档 + 测试为准。
