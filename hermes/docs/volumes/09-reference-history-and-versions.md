# 卷九 · 参考：索引与维护

> **卷标准**：[`VOLUME_STANDARD.md`](VOLUME_STANDARD.md) §5.9（**索引卷**，不要求 E2E 时序） · **完成度**：[`MANIFEST.md`](MANIFEST.md)  
> **本卷边界**：卷间导航、完成度与验收方式；**运行时路径只读卷一～八正文**。  
> **相邻卷**：[MANIFEST](MANIFEST.md)

---

## 本卷目录

| 块 | 节 | 作用 |
|----|-----|------|
| **导航** | [§1](#1-卷一八主题与权威-节) | 每卷写什么、去哪节 grep |
| **验收** | [§2](#2-完成度与怎么验) | MANIFEST 状态；不靠口头「达标」 |
| **维护** | [§3](#3-改文档时改哪里) | 增量索引；与 `HERMES.md` 同步 |

### 目录（锚点跳转）

- **§1** [卷一～八主题与权威 §](#1-卷一八主题与权威-节)  
- **§2** [完成度与怎么验](#2-完成度与怎么验)  
- **§3** [改文档时改哪里](#3-改文档时改哪里)

---

## 1. 卷一～八主题与权威 §

**全书大纲**（第1–8章 + 附录，可点击）：[MANIFEST — 📋 总目录](MANIFEST.md#-总目录全书)。

读任何能力前，先打开对应卷的 **[本卷目录](#本卷目录)**，或从上表总目录跳进具体锚点。

| 卷 | 主题 | 权威 §（优先 grep 这里） |
|----|------|--------------------------|
| [01](01-platform-and-architecture.md#sec-ch1) | **项目整体**：模块地图、三张整体图、入口/queue/权威表 | §1.1–1.6、§2、§2.5 |
| [02](02-surface-and-presentation.md#本卷目录) | TUI/Desktop/CLI 呈现、`_agent_cbs`、ACP、compute host | §3.4、§5.2、§5.4.1、§11–§12 |
| [03](03-runtime-session-and-loop.md#本卷目录) | 循环、`turn_*`、**压缩方案**、Session/Memory/HITL | [第2–3章](03-runtime-session-and-loop.md#sec-ch2)、[第4章](03-runtime-session-and-loop.md#sec-ch4)、[第6章](03-runtime-session-and-loop.md#sec-ch6)、[第5章 Batch/Codex](03-runtime-session-and-loop.md#sec-ch5) |
| [04](04-prompt-and-context.md#本卷目录) | system 三段、每 API 组装、context engine | §0.7、§4.5–§4.7 |
| [05](05-capabilities-extensions.md#本卷目录) | 工具/MCP/Skills/记忆执行 | §3、§4 |
| [06](06-gateways-channels-and-hitl.md#本卷目录) | IM、`busy_input_mode`、cron、Room | §3、§5–§6 |
| [07](07-multi-agent-and-kanban.md#本卷目录) | delegate、kanban worker、MoA | §3–§5 |
| [08](08-security-and-governance.md#本卷目录) | 扫描、审批、background review | §2–§3 |

外部对照（非 Hermes 运行时）：[`CHANNEL_AGENTSCOPE_VS_HERMES.md`](../../compare/CHANNEL_AGENTSCOPE_VS_HERMES.md)。

---

## 2. 完成度与怎么验

全表与状态列：[MANIFEST.md — 完成度](MANIFEST.md#完成度)。

1. 看 **状态列**（达标 / 部分达标 / 索引）。  
2. 打开该卷 **本卷目录**，确认是否有 §0、§3 E2E、权威表（卷九除外）。  
3. 权威表里的符号 → `hermes-agent` 里 `rg`；对不上就改卷或降 MANIFEST 状态。  
4. 增量阅读：[MANIFEST — 近期增量索引](MANIFEST.md#近期增量索引不必重读整卷)。

---

## 3. 改文档时改哪里

| 改了什么 | 同步 |
|----------|------|
| 新增/重命名 § | 该卷 **本卷目录** 块表 + 锚点列表 |
| 一卷达到/失去「达标」 | [MANIFEST](MANIFEST.md) 状态列 |
| 总览要点 | [`HERMES.md`](../HERMES.md) 对应章索引 |
| 卷标准本身 | [`VOLUME_STANDARD.md`](VOLUME_STANDARD.md) |

`archive/legacy/` 仅作历史对照；与卷冲突时 **以卷 + 源码为准**。


---

<a id="source-supplement"></a>

## 增补：当前源码快照与增量文档维护

历史演进用于解释背景，当前行为要由源码判定。本轮核对的是本地提交 `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd`，不是远端最新版本保证。

- [全书大纲](README.md)：现为原九卷加四个后端/运行支撑专卷；记忆两份参考仍保留。
- [覆盖审计](SOURCE_AUDIT.md)：模块族、补齐专题、未覆盖深潜与建议优先级。
- [源码清单](SOURCE_INVENTORY.json)：受 Git 管理的代码文件、hash、Python 符号与阅读导航；L0 清点而非逐行理解。
- [引用证据](SOURCE_EVIDENCE.json)：新增专题的精确源码符号与快照内行号。
- [写作标准](VOLUME_STANDARD.md)：证据等级、图含义、增量维护与验收。
- [变更总结](CHANGES.md)：本轮编辑范围、保全和验证结果。

源码升级后先运行 audit 的 `--check` 发现变化，再审阅实现/文档并更新；不可只刷新 hash 就宣称设计已经跟上。老归档合卷脚本会覆盖手工增补，日常不要开启其重建开关。现行维护流程见 [CATALOG 增补](../CATALOG.md#source-supplement)。
