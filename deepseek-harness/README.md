# DeepSeek Harness — 设计文档目录（doc-sn）

> 学习用中文文档。权威行为以官方 `docs/`、包 README、测试为准。  
> **怎么读（治「水」）**：  
> 1. **[00-流程与概念对照](./00-流程与概念对照.md)** — 一条调用链写了什么  
> 2. **[00b-顶层设计与实体边界](./00b-顶层设计与实体边界.md)** — 谁封装什么、边界在哪  
> 再按需翻介绍 / 全景 / PART / source。

---

## 推荐阅读顺序

```text
① 流程细节        00-流程与概念对照.md
①′ 实体边界        00b-顶层设计与实体边界.md   ← 顶层设计 / 封装表 / 类图
② 术语表          GLOSSARY.md
③ 项目介绍        01-…
④ 总体架构        02-…（发消息细节以 00 为准）
⑤–⑥ 全景与场景    03 / 04
⑥′ 运行时深度      06-运行时深度专题-Memory压缩投影HITL.md
⑥″ HITL 专题       07-HITL审批流程详解.md   ← 看不懂暂停/恢复先看这篇
⑦ 机制 PART1–3
⑧′ 与 Pi 对照      05-对照-Pi-与-DSH.md
⑨ 源码            source/
```

**禁止**只靠 02 里几张时序图当「懂了架构」——缺封装边界请回 **00b**。

---

## 总目录

### 入门

| 序号 | 文档 | 内容 |
|------|------|------|
| **0** | [00-流程与概念对照.md](./00-流程与概念对照.md) | 逐步 Session 写入、新词对照、固定 vs 插件 |
| **0b** | [00b-顶层设计与实体边界.md](./00b-顶层设计与实体边界.md) | **顶层目标、实体拥有/不拥有、类图、决策树** |
| 1 | [GLOSSARY.md](./GLOSSARY.md) | 术语展开 |
| 2 | [01-项目介绍与设计思路.md](./01-项目介绍与设计思路.md) | 定位与动机 |
| 3 | [02-总体架构与端到端.md](./02-总体架构与端到端.md) | 分层与启动 E2E |
| 4 | [03-子系统全景.md](./03-子系统全景.md) | 广度 |
| 5 | [04-关键场景详解.md](./04-关键场景详解.md) | 场景 |
| 6 | [06-运行时深度专题-Memory压缩投影HITL.md](./06-运行时深度专题-Memory压缩投影HITL.md) | Memory / 压缩 / 投影 / HITL / Trajectory / 框架对照 / Cordis |
| 7 | [07-HITL审批流程详解.md](./07-HITL审批流程详解.md) | **审批 HITL 从零看懂**（暂停=await、恢复=RPC） |

### 机制与对照

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | **~1.7k 行**：Cordis/Profile/Turn/Session/Inbox；实体表+写入归属 |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | **~1.0k 行**：Seam/执行世界/Skills/Subagent/审批 |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | **~1.0k 行**：包地图/表面/持久化/vs MAF·Penguin·Pi |
| [05-对照-Pi-与-DSH.md](./05-对照-Pi-与-DSH.md) | 与 Pi：loop、Session、投影 |
| [CORE_RUNTIME.md](./CORE_RUNTIME.md) / [source/](./source/README.md) | 速查与源码走读 |

---

## 质量要求（写 doc-sn 时）

- 必须有 **实体拥有/不拥有** 或链到 00b  
- 流程必须有 **写入归属** 或链到 00  
- 新词必须有 **熟悉对照**  
- **禁止**只有流程图、无封装说明  

（与 `penguin-harness/doc-sn/DOC_QUALITY.md` 同标准。）

---

## 与官方 docs/

| | 官方 `docs/` | `doc-sn/` |
|--|-------------|----------|
| 用途 | 权威、短、双语 | 学习向；00/00b 偏流程与边界 |
| 门禁 | `doc-sync` | 不参与 |
