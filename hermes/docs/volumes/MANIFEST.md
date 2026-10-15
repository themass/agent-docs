# 各卷

**写作标准**（结构、权威表、时序图、与 `HERMES.md` 同步）：[`VOLUME_STANDARD.md`](VOLUME_STANDARD.md)  
**范本卷**：[02-surface-and-presentation.md](02-surface-and-presentation.md)

每卷目标顺序：**总分总** — **§1 总述** → **§2… 分述**（架构 / E2E / 权威表）→ **末 § 总收**（读哪卷、grep）；易混概念放在 **相关分述节**，不以「先澄清」开篇。  
**目录跳转**：文首 **[本卷目录](#各卷目录)** 使用显式锚点（卷一 `#sec-*`）；点击应落到对应节。

全书章序对齐 [OpenHands SDK ARCHITECTURE_PART1](../../openhands-sdk/ARCHITECTURE_PART1.md) 的 **第1–8章 + 附录** 叙事（概览 → 核心/会话 → 工具 → 端到端 → Memory → 多 Agent → Plan/治理），Hermes 按 **多入口 + 分卷** 展开。

## 📋 总目录（全书）

- [第1章：项目概览与 Hermes 整体架构](01-platform-and-architecture.md#sec-ch1)（**卷一**）
  - [1.1 产品能力](01-platform-and-architecture.md#sec-1-1) · [1.2 仓库模块地图](01-platform-and-architecture.md#sec-1-2)
  - [1.3 核心模块关系](01-platform-and-architecture.md#sec-1-3) · [1.4 关键组件](01-platform-and-architecture.md#sec-1-4)
  - [1.5 四层运行时](01-platform-and-architecture.md#sec-1-5) · [1.6 端到端](01-platform-and-architecture.md#sec-1-6) · [1.7 数据流全景](01-platform-and-architecture.md#sec-1-7)
  - [1.8 整体类图](01-platform-and-architecture.md#sec-1-8) · [1.9 facade 两层](01-platform-and-architecture.md#sec-1-9) · [1.10 pm/插件/cron](01-platform-and-architecture.md#sec-1-10)
  - [**1.11 Session 模块**](01-platform-and-architecture.md#sec-1-11) · [**1.12 Memory 模块**](01-platform-and-architecture.md#sec-1-12)
  - [第2章 多入口与权威表](01-platform-and-architecture.md#sec-ch2) — [2.3 忙时 queue](01-platform-and-architecture.md#sec-2-3) · [2.4 权威表](01-platform-and-architecture.md#sec-2-4) · [2.5 平行入口](01-platform-and-architecture.md#sec-2-5)
  - [第3章 卷间索引](01-platform-and-architecture.md#sec-ch3)
- [第2章：Surface 呈现与 callback](02-surface-and-presentation.md#本卷目录)（卷二）
  - [2.1 架构：CLI vs tui_gateway](02-surface-and-presentation.md#1-架构) · [2.2 三种 id](02-surface-and-presentation.md#22-三种会话标识_agent_cbssid-里的-sid-是哪一个)
  - [2.3 TUI/Desktop 一轮 E2E](02-surface-and-presentation.md#34-端到端时序platform-callback-与-plugin-hook-同图) · [3.0 忙时 `queued_prompt`](02-surface-and-presentation.md#30-忙时再点发送用户话排队不是-messagedelta-的-queuedelta)
  - [2.4 `_agent_cbs` 权威表](02-surface-and-presentation.md#52-_agent_cbssid-返回的-dict-里有什么) · [2.5 callback vs hook](02-surface-and-presentation.md#57-platform-callback-与-plugin-hook-为什么两套都有)
  - [2.6 compute host · ACP](02-surface-and-presentation.md#11-compute-hostturn-隔离子进程) · [§12 ACP](02-surface-and-presentation.md#12-acpide-呈现与忙时策略)
- [第3章：运行时与会话循环](03-runtime-session-and-loop.md#本卷目录)（卷三）
  - [一轮是什么：会话、迭代、租约、id](03-runtime-session-and-loop.md#sec-ch1) · [跟进队列不在 while 里](03-runtime-session-and-loop.md#sec-1-6)
  - [一轮从进门走到 finalize_turn](03-runtime-session-and-loop.md#sec-ch2) · [turn_*.py 每个文件管哪一段](03-runtime-session-and-loop.md#sec-ch3)
  - [压缩方案（阈值、原地/裂变、4.4 例子）](03-runtime-session-and-loop.md#sec-ch4) · [Batch 和 Codex](03-runtime-session-and-loop.md#sec-ch5)
  - [Session / Memory / HITL / 裂变](03-runtime-session-and-loop.md#sec-ch6) — [6.3 HITL](03-runtime-session-and-loop.md#sec-6-3) · [6.4 Memory](03-runtime-session-and-loop.md#sec-6-4) · [6.7 SessionDB 行长什么样](03-runtime-session-and-loop.md#sec-6-7)
- [第4章：Tool / Skills / MCP](05-capabilities-extensions.md#本卷目录)（卷五）
  - [4.1 工具轮 E2E](05-capabilities-extensions.md#3-端到端一次工具轮hook--callback-点位) · [4.2 权威表](05-capabilities-extensions.md#4-权威表)
- [第5章：端到端流程（完整）](01-platform-and-architecture.md#sec-1-4)
  - [5.1 三张整体图权威在卷一](01-platform-and-architecture.md#sec-ch1) · [5.2 汇合前 queue](01-platform-and-architecture.md#sec-2-3)
  - [5.3 内核放大](../HERMES.md#3-内核时序不是端到端) → [卷三第2章](03-runtime-session-and-loop.md#sec-ch2)
- [第6章：Prompt / Memory 与运行时 Message](04-prompt-and-context.md#本卷目录)（卷四 + 卷五 §4.4）
  - [6.1 system 三段与 invalidate](04-prompt-and-context.md#02-三段-tierstable--context--volatile) · [6.2 每 API 组装](04-prompt-and-context.md#45-每迭代-assemble_api_request-顺序api-上下文-build)
  - [6.3 压缩方案](03-runtime-session-and-loop.md#sec-ch4) · [6.4 Memory 运行时](03-runtime-session-and-loop.md#sec-6-4) · [记忆工具写盘](05-capabilities-extensions.md#44-记忆)
- [第7章：多 Agent、Kanban 与 MoA](07-multi-agent-and-kanban.md#本卷目录)（卷七）
  - [7.1 `delegate_task` E2E](07-multi-agent-and-kanban.md#3-端到端delegate_taskhook--呈现) · [7.2 看板 worker](07-multi-agent-and-kanban.md#4-看板-worker-端到端) · [7.3 MoA](07-multi-agent-and-kanban.md#5-moa多模型参考仍是一轮父-agent)
- [第8章：Gateway、安全与 Plan](06-gateways-channels-and-hitl.md#本卷目录)（卷六 + 卷八 + 卷四 Plan）
  - [8.1 IM 收发与 busy](06-gateways-channels-and-hitl.md#3-端到端收一条含-busy-queue) · [8.2 cron / Room](06-gateways-channels-and-hitl.md#5-cron定时任务与-delivery_queue)
  - [8.3 审批与扫描](08-security-and-governance.md#2-端到端危险终端命令cli--im) · [8.4 background review](08-security-and-governance.md#3-后台复盘background-review)
  - [8.5 Plan / Kanban 在提示中的形态](04-prompt-and-context.md#06-plancoordinatorkanban在提示里是什么形态)
- [附录：索引与对照](09-reference-history-and-versions.md#本卷目录)（卷九）
  - [与 AgentScope 通道对照](../../compare/CHANNEL_AGENTSCOPE_VS_HERMES.md)

## 各卷目录（文首跳转）

| 卷 | 目录 |
|----|------|
| 01 | [本卷目录](01-platform-and-architecture.md#本卷目录) |
| 02 | [本卷目录](02-surface-and-presentation.md#本卷目录) |
| 03 | [本卷目录](03-runtime-session-and-loop.md#本卷目录) |
| 04 | [本卷目录](04-prompt-and-context.md#本卷目录) |
| 05 | [本卷目录](05-capabilities-extensions.md#本卷目录) |
| 06 | [本卷目录](06-gateways-channels-and-hitl.md#本卷目录) |
| 07 | [本卷目录](07-multi-agent-and-kanban.md#本卷目录) |
| 08 | [本卷目录](08-security-and-governance.md#本卷目录) |
| 09 | [本卷目录](09-reference-history-and-versions.md#本卷目录) |

## 完成度

| 卷 | 文件 | 状态 | 已有 | 待按标准补齐（摘要） |
|----|------|------|------|----------------------|
| 01 | [01-platform-and-architecture.md](01-platform-and-architecture.md) | **达标** | 第1章：模块地图+四层架构+端到端+类图+两层 facade；第2章入口/queue/表 | 与 HERMES §2 同步 |
| 02 | [02-surface-and-presentation.md](02-surface-and-presentation.md) | **达标** | 文首目录；§0–§12；§5.2/5.4.1、§3.4 | 维护与源码同步即可 |
| 03 | [03-runtime-session-and-loop.md](03-runtime-session-and-loop.md) | **达标** | 第1–3章循环；第4章压缩；第6章 Session/Memory/HITL | provider 配置见 [卷五附录](05-memory-system-reference.md) |
| 04 | [04-prompt-and-context.md](04-prompt-and-context.md) | **部分达标** | 机制正文 + [Prompt 原文库](04-prompt-corpus.md) | context_engine 插件深潜仍读源码 |
| 05 | [05-capabilities-extensions.md](05-capabilities-extensions.md) | **达标** | §0–§4 工具轮；[附录 A Memory](05-memory-system-reference.md)、[附录 B 架构/进化](05-memory-architecture-and-evolution.md) | 与 `tool_executor` / provider / curator 同步 |
| 06 | [06-gateways-channels-and-hitl.md](06-gateways-channels-and-hitl.md) | **部分达标** | 第7章门户；[第8章 IM 审批](06-gateways-channels-and-hitl.md#sec-g8)（阻塞/pending/slash/通道皮） | 各通道 SDK 字段仍以适配器源码为准 |
| 07 | [07-multi-agent-and-kanban.md](07-multi-agent-and-kanban.md) | **部分达标** | §0 三分法；delegate E2E；kanban/MoA；镜像 hook 表 | MoA 配置细节可再扩 |
| 08 | [08-security-and-governance.md](08-security-and-governance.md) | **部分达标** | §2 审批双路径+CLI/Gateway；§3 复盘 spawn/预算/fork 表 | 与 `approval.py` / `background_review.py` 同步 |
| 09 | [09-reference-history-and-versions.md](09-reference-history-and-versions.md) | **索引卷** | 版本/对照 | 轻量标准即可；链到各卷权威 § |

状态含义：**达标** = 满足 `VOLUME_STANDARD.md` 第 1–3 节；**骨架** = 有图无 §0/权威表/完整 E2E；**待升** = 需对照标准重写或扩写。

## 还缺多少？怎么验（别信口号，信对照方式）

**诚实估计（维护视角，见 MANIFEST 状态列）**：**达标**：01、02、03、05；**部分达标**：04、06、07、08；**索引**：09。目标仍是 **主路径符号可 grep**，不是百科全覆。

### 按「用户关心的能力」覆盖度（粗）

| 能力域 | 卷 | 文档状态 | 仍缺什么（举例） |
|--------|-----|----------|------------------|
| TUI/Desktop 呈现、callback/hook 表 | 02 | **可信为主** | 与源码漂移时需对着 §5.2 grep |
| `run_conversation` 内核、租约、`turn_*` | 03 | **可信为主** | 边缘 recovery/Codex 支路需读源码注释 |
| System + 每 API 上下文车道 | 04 | **部分** | context_engine 各插件、tool_search 动态表 |
| 记忆/工具/Skills/MCP **执行** | 05 | **达标为主** | 见卷五 §3–4 |
| IM 收发、busy queue、Delivery | 06 | **部分** | 审批 → 卷八 |
| delegate / kanban / MoA | 07 | **部分** | 卷七 §3–5 |
| 审批、扫描、后台复盘 | 08 | **部分→加厚** | [卷八 §2–3](08-security-and-governance.md#2-端到端危险终端命令cli--im) · [卷六 §8](06-gateways-channels-and-hitl.md#sec-g8) |
| 多入口汇合、进程模型 | 01 | **达标** | §0.4、§3.2、§4 |
| queue / steer（用户跟进） | 01+02+03 §1.6 | **专题已写** | IM 细节见卷六 §5；无 Pi 式内核 inbox |
| 考古长文 | `archive/legacy/` | **全但可能旧** | 与卷冲突时 **以卷+源码为准**（卷头已写） |

### 建议你用的验证法（比「信 AI」可靠）

1. **看 MANIFEST 状态列** — 「骨架」= 不要当完整规范；「达标」= 应按 `VOLUME_STANDARD` 有 §0 + E2E + 权威表。  
2. **权威表行 → 源码** — 卷内写的函数名/配置键，在 `hermes-dev/hermes-agent` 里 `rg '符号名'`；对不上就是文档落后或写错。  
3. **分层读图** — [卷三 §1.1](03-runtime-session-and-loop.md#11-图里的名字是函数还是对象为什么在别的端到端图里没见过) 说明 **产品 E2E 故意不画** 的门外队列、门内 `turn_*`；缺块时先想「该在哪一层」而不是「图漏了」。  
4. **legacy 当附录** — `PROMPT_SYSTEM_ARCHITECTURE.md` 等很全，但 **不自动等于当前行为**；以卷四/卷五达标章节 + grep 为准。  
5. **单点怀疑** — 把你关心的路径写成「入口函数 → 下一跳函数」链，让文档只负责 **对齐这条链**；链外的一律标「未收录」而不是假装有了。

### 文档维护承诺（可检查的）

- 状态只在 [MANIFEST](MANIFEST.md) 改；夸大「达标」会破坏你自己的 grep 验收。  
- 增量写在 [近期增量索引](#近期增量索引不必重读整卷)，避免逼你重读整卷。  
- 与源码冲突时：**修卷或改 MANIFEST 状态**，不留在正文里两套说法（卷二 §5.2 权威表原则）。

你若要 **可审计的完成度**，下一步应按 `VOLUME_STANDARD` §5 依次 **卷五 → 卷六 → 卷一** 拉到「达标」；每卷交付物就是上表「仍缺什么」列的清空。

### 近期增量索引（不必重读整卷）

若你 **已读过旧版**，只补下面几段即可（按主题跳转）。

| 主题 | 读哪里 | 讲了什么 |
|------|--------|----------|
| **用户消息 queue / steer**（不是 token 队列） | [卷一 §2.3](01-platform-and-architecture.md#sec-2-3) | 进门之前；IM/CLI/TUI；admission 图 |
| **为何卷三 E2E 没画 queue** | [卷三 §1.6](03-runtime-session-and-loop.md#06-用户消息队列-不在-本卷-while-里为何端到端图看不见) | 队列在 `run_conversation` 门外；§1.1 分层表多了一行 |
| **TUI 忙时再 submit** | [卷二 §3.0](02-surface-and-presentation.md#30-忙时再点发送用户话排队不是-messagedelta-的-queuedelta) | `queued_prompt` / `_drain_queued_prompt` 时序；与 `queueDelta` 区分 |
| **总览图注** | [HERMES.md §2.1](HERMES.md#21-端到端流程图) 段首 | 汇合前 queue/steer 一句 + 链到上面三节 |
| **系统提示 + API 全上下文** | [卷四 §0.7、§4.5–4.8、§7](04-prompt-and-context.md#07-发给模型的一次请求不止-system-字符串) | 车道图；memory/hook → [原文库 §4](04-prompt-corpus.md#4-主-agentuser-侧车与围栏原文) |
| **Prompt 长原文 / 子 Agent 样例** | [04-prompt-corpus.md](04-prompt-corpus.md) | 中文默认 system、围栏、插件帧 |
| **工具轮 dispatch / MCP** | [卷五 §3–4](05-capabilities-extensions.md#3-端到端一次工具轮hook--callback-点位) | `run_tool_round` → `handle_function_call` |
| **IM busy queue / steer** | [卷六 §0.1、§3](06-gateways-channels-and-hitl.md#01-im-忙时busy_input_mode用户跟进队列) | `_pending_messages` + `busy_input_mode` |
| **delegate / 看板 / MoA** | [卷七 §0、§3–5](07-multi-agent-and-kanban.md#0-先澄清三种多-agent别混) | 同进程子 Agent vs 子进程 worker |
| **压缩方案 + 例子** | [卷三第4章](03-runtime-session-and-loop.md#sec-ch4) | 阈值、in_place vs 裂变、[4.4 举例](03-runtime-session-and-loop.md#sec-4-example) |
| **Session / Memory / HITL** | [卷三第6章](03-runtime-session-and-loop.md#sec-ch6) | 6.3 闸门；6.4 三层记忆；6.7 库行形状 |
| **Memory 使用 + Provider 清单** | [卷五附录 A](05-memory-system-reference.md) | legacy §7–§8；运行时仍看卷三 6.4 |
| **Memory 协作 + Skills/Curator/Trajectory** | [卷五附录 B](05-memory-architecture-and-evolution.md) | legacy §6、§9、附录六层 |
| **IM 审批卡（阻塞/pending）** | [卷六第8章](06-gateways-channels-and-hitl.md#sec-g8) | notify / Event / slash |
| **审批 + 后台复盘（内核）** | [卷八 §2–3](08-security-and-governance.md#2-端到端危险终端命令cli--im) | 复盘端到端：[§3.0](08-security-and-governance.md#sec-8-br-flow) |
| **平行入口索引** | [卷一 §2.5](01-platform-and-architecture.md#sec-2-5) | delegate/cron/ACP/Batch/Room/Codex/compute host → 各卷专节 |
| **cron / Room** | [卷六 §5–6](06-gateways-channels-and-hitl.md#5-cron定时任务与-delivery_queue) | `run_job`、`delivery_queue`、hosted room driver |
| **Batch / Codex** | [卷三 §5.0 分叉图](03-runtime-session-and-loop.md#sec-5-0) · [§5.1 Batch](03-runtime-session-and-loop.md#sec-5-1) · [§5.2 Codex](03-runtime-session-and-loop.md#sec-5-2) | Batch 仍 `while`；仅 `api_mode=codex_app_server` 跳过 `while` |
| **ACP / compute host** | [卷二 §11–12](02-surface-and-presentation.md#11-compute-hostturn-隔离子进程) | turn 隔离子进程；IDE ACP 流 |

## 各卷主题（一句话）

| 卷 | 讲什么 |
|----|--------|
| [01](01-platform-and-architecture.md) | 一次对话从哪进来，汇到 `AIAgent.run_conversation` |
| [02](02-surface-and-presentation.md) | 终端和 TUI/Desktop 怎么把这一轮画出来（**范本**） |
| [03](03-runtime-session-and-loop.md) | 门禁、循环、会话库、压缩 |
| [04](04-prompt-and-context.md) | 系统提示三段，以及为什么中途不改 |
| [05](05-capabilities-extensions.md) | 记忆、工具、技能、MCP |
| [06](06-gateways-channels-and-hitl.md) | IM 收发，危险命令等人点头 |
| [07](07-multi-agent-and-kanban.md) | 对话里的子 Agent，看板上的 worker |
| [08](08-security-and-governance.md) | 安装扫描、执行审批、后台复盘 |
| [09](09-reference-history-and-versions.md) | 版本和对照教材的索引，不是运行时路径 |


---

<a id="source-supplement"></a>

## 增补：十三卷导航、覆盖证据与维护约定

原九卷目录与历史状态表保留。新增专题不替换原卷；**全书现行阅读入口是 [README](README.md)**，包含十三卷大纲和问题索引。

| 新增/扩写 | 补上什么 | 入口 |
|---|---|---|
| 卷十 | 推理服务商声明、Transport、credential pool、fallback、辅助请求与协议回放 | [10](10-model-backends-and-resilience.md) |
| 卷十一 | 终端环境工厂、shell/cwd、隔离、guard、前后台与退出清理 | [11](11-terminal-execution-backends.md) |
| 卷十二 | Cron 时间槽、执行/交付账本、unknown、PM worker/安装/发布 | [12](12-automation-and-package-runtime.md) |
| 卷十三 | 配置归属、秘密隔离、平台事实、日志/监控边界 | [13](13-config-secrets-and-observability.md) |
| 卷五新增 §7 | 插件能力注册、profile scope、替换/卸载所有权、并发 loader | [05 §7](05-capabilities-extensions.md#cap-plugin-lifecycle) |
| 卷七新增 §6 | delegate/public lifecycle/Kanban/MoA 边界与进程内 handle | [07 §6](07-multi-agent-and-kanban.md#multi-runtime-boundaries) |

**旧“达标”不是源码全覆盖证明。** [写作标准](VOLUME_STANDARD.md#standard-depth) 区分 L0 清点、L1 导航、L2 源码专题、L3 运行验证；本轮没有新增 L3。新增专题有哪些证据、哪些模块仍缺深潜，见 [SOURCE_AUDIT](SOURCE_AUDIT.md)；文件/符号事实在 [源码清单](SOURCE_INVENTORY.json) 与 [引用证据](SOURCE_EVIDENCE.json)。

维护时直接编辑卷，勿执行覆盖式 legacy 重建。具体命令与保全验收见 [变更总结](CHANGES.md) 和 [维护流程增补](../CATALOG.md#source-supplement)。
