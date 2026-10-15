# Hermes 单篇教程：总览、核心链路、模块设计与历史参考

**阅读导航**：每篇文首都有展开的目录；跨篇内容归属与迁移清单见 [目录与主题归属整理](REVIEW_AND_CHANGES.md#outline-topic-moves)。

这套文档保留旧版清晰的讲述方式：**先看整体职责，再沿真实流程穿起来，最后进入模块与代码细节**。本轮没有把它重新拼成分卷，也没有删除长篇教程、图表和设计讨论；重点修正会影响理解的过时结论，并把“当前实现”“历史示例”“外部参考”分开。

> **源码核对基线**：`hermes-dev/hermes-agent`，commit `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd`。\
> **校订日期**：2026-10-15。旧文首的 0.19.0 / 2026-07 等是原稿身份，不代表本次最新安装版本。\
> **范围说明**：重点链路已核对；25 篇旧文件均整理了导航/适用范围与链接，但不是约三万行旧源码摘录的逐行认证，详见 [校订记录](REVIEW_AND_CHANGES.md)。

<a id="1-先读哪几篇三条阅读路线"></a>
<a id="section-1"></a>

<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 先读哪几篇：三条阅读路线](#section-1)
  - [1.1 路线 A：第一次了解 Hermes](#section-1-1)
  - [1.2 路线 B：沿数据流理解系统](#section-1-2)
  - [1.3 路线 C：研究长任务与人机协作](#section-1-3)
- [2. 第一部分：整体架构与入口](#section-2)
- [3. 第二部分：一轮推理、消息状态与上下文](#section-3)
- [4. 第三部分：记忆、工具与扩展能力](#section-4)
- [5. 第四部分：多代理、Kanban 与协作](#section-5)
- [6. 第五部分：安全、审批与人工交互](#section-6)
- [7. 第六部分：设计参考、版本与维护](#section-7)
- [8. 按问题找答案](#section-8)
- [9. 归档与现行分卷的关系](#section-9)
<!-- visible-toc:end -->

## 1. 先读哪几篇：三条阅读路线

<a id="路线-a第一次了解-hermes"></a>
<a id="section-1-1"></a>
### 1.1 路线 A：第一次了解 Hermes

[整体架构](ARCHITECTURE.md) → [当前实现导读](CURRENT_IMPLEMENTATION.md) → [Agent Loop](AGENT_LOOP_ARCHITECTURE.md) → [Prompt](PROMPT_SYSTEM_ARCHITECTURE.md) → 选择一个具体模块。

<a id="路线-b沿数据流理解系统"></a>
<a id="section-1-2"></a>
### 1.2 路线 B：沿数据流理解系统

[启动恢复](CURRENT_IMPLEMENTATION.md#current-restore) → [工作区消息与请求投影](CURRENT_IMPLEMENTATION.md#current-messages) → [普通 flush](CURRENT_IMPLEMENTATION.md#current-flush) → [压缩提交](CURRENT_IMPLEMENTATION.md#current-compaction) → [State / Auxiliary](STATE_AND_AUXILIARY.md)。

<a id="路线-c研究长任务与人机协作"></a>
<a id="section-1-3"></a>
### 1.3 路线 C：研究长任务与人机协作

[入口与 Gateway](CLI_GATEWAY_SYSTEM.md) → [多代理](MULTI_AGENT_ARCHITECTURE.md) → [Kanban](KANBAN_MULTIAGENT_DEEP_ANALYSIS.md) → [人工审批](HITL_APPROVAL_FLOW.md) → [安全防线](SECURITY_SCAN_DEEP_ANALYSIS.md)。

<a id="part-architecture"></a>
<a id="2-第一部分整体架构与入口"></a>
<a id="section-2"></a>
## 2. 第一部分：整体架构与入口

| 文档 | 回答的问题 | 阅读边界 |
|---|---|---|
| [ARCHITECTURE](ARCHITECTURE.md) | 入口、引擎、工具、状态为什么这样分层？ | 先看全景/设计原则，再查模块地图；旧精确行号按历史索引 |
| [SURFACE_ARCHITECTURE](SURFACE_ARCHITECTURE.md) | CLI/TUI/Desktop/桥接层分别负责什么？ | Surface 不等于 Agent 内核；旧 UI 事件未运行验证 |
| [CLI_GATEWAY_SYSTEM](CLI_GATEWAY_SYSTEM.md) | 消息怎样进入系统、驱动 Agent、再送回用户？ | 当前 channel 生命周期/followup 另见现行卷六 |
| [TELEGRAM_MULTISSESSION_TOPICS](TELEGRAM_MULTISSESSION_TOPICS.md) | Topic 怎样绑定和路由不同 Session？ | Topic 不是 Kanban，不提供独立 Profile memory 或 OS 隔离 |

<a id="part-runtime"></a>
<a id="3-第二部分一轮推理消息状态与上下文"></a>
<a id="section-3"></a>
## 3. 第二部分：一轮推理、消息状态与上下文

| 文档 | 回答的问题 | 建议读法 |
|---|---|---|
| [CURRENT_IMPLEMENTATION](CURRENT_IMPLEMENTATION.md) | 哪些核心事实已随当前源码校订？ | 先读；12 个问题覆盖本轮重点链路 |
| [AGENT_LOOP_ARCHITECTURE](AGENT_LOOP_ARCHITECTURE.md) | AIAgent、ReAct、工具、steer、压缩怎样协作？ | 总览→状态→循环→Prompt→工具→恢复 |
| [STATE_AND_AUXILIARY](STATE_AND_AUXILIARY.md) | 消息持久化与辅助模型调用由谁负责？ | 新增恢复/普通 flush/压缩提交对照 |
| [PROMPT_SYSTEM_ARCHITECTURE](PROMPT_SYSTEM_ARCHITECTURE.md) | system/user/API 请求分别怎样组装？ | 注入顺序和 sidecar 已校订，层数只是解释视角 |
| [SUBAGENT_RUNTIME_PROMPT_EXAMPLE](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md) | 子代理的实际 Prompt 样本怎样对应设计？ | 单次历史样本，不是所有请求的固定模板 |
| [EXECUTION_FLOW_ANALYSIS](EXECUTION_FLOW_ANALYSIS.md) | 用一份长代码讲解把一次执行串起来 | 历史考古与教学材料；结合当前导读定位迁移后的模块 |

<a id="part-capabilities"></a>
<a id="4-第三部分记忆工具与扩展能力"></a>
<a id="section-4"></a>
## 4. 第三部分：记忆、工具与扩展能力

| 文档 | 回答的问题 | 容易混淆的地方 |
|---|---|---|
| [MEMORY_SYSTEM](MEMORY_SYSTEM.md) | 什么长期保存？如何预取、检索与提交？ | built-in files / Session Search / 外部 Provider；压缩不是全部记忆 |
| [TOOLS_SYSTEM](TOOLS_SYSTEM.md) | 怎样注册、筛选、执行工具并处理大结果？ | 暴露 schema、执行中间件、结果预算是不同阶段 |
| [SKILLS_SYSTEM](SKILLS_SYSTEM.md) | 技能怎样发现、加载、安装、写入与后台自进化？ | 含 skill_manage、Background Review 与 Curator 的职责边界 |
| [MCP_INTEGRATION](MCP_INTEGRATION.md) | 远端能力如何接入、鉴权和执行？ | 协议能力不等于 Hermes 当前全部实现 |
| [PLUGINS_SYSTEM](PLUGINS_SYSTEM.md) | Hook 和其它扩展点怎样组合？ | pre_llm_call 不改 system 缓存；api_content 可持久化 |

<a id="part-collaboration"></a>
<a id="5-第四部分多代理kanban-与协作"></a>
<a id="section-5"></a>
## 5. 第四部分：多代理、Kanban 与协作

| 文档 | 回答的问题 | 关键区别 |
|---|---|---|
| [MULTI_AGENT_ARCHITECTURE](MULTI_AGENT_ARCHITECTURE.md) | 主/子代理怎样共用引擎又各自持有状态？ | 当前 delegate 不共享父预算对象；未配置默认 250 |
| [KANBAN_MULTIAGENT_DEEP_ANALYSIS](KANBAN_MULTIAGENT_DEEP_ANALYSIS.md) | 任务图怎样调度、claim、启动 worker、审核和通知？ | Task、Run、worker Session 分开；进程成功退出不自动等于任务完成 |

<a id="part-security"></a>
<a id="6-第五部分安全审批与人工交互"></a>
<a id="section-6"></a>
## 6. 第五部分：安全、审批与人工交互

| 文档 | 回答的问题 | 关键区别 |
|---|---|---|
| [SECURITY_SCAN_DEEP_ANALYSIS](SECURITY_SCAN_DEEP_ANALYSIS.md) | 外部内容在哪些阶段扫描和拦截？ | 安装扫描、上下文加载、运行告警、执行审批不是同一层 |
| [HITL_APPROVAL_FLOW](HITL_APPROVAL_FLOW.md) | 危险工具为何停住？人怎样回答？工具如何继续？ | Queue/Event 同栈继续不等于重启 restore；request_id 不是 tool_call_id |

<a id="part-reference"></a>
<a id="7-第六部分设计参考版本与维护"></a>
<a id="section-7"></a>
## 7. 第六部分：设计参考、版本与维护

下列材料保留其推理价值，但不作为当前源码已实现功能或当前产品排名的证据。

| 文档 | 内容与适用范围 |
|---|---|
| [LANGGRAPH_DESIGN_PRINCIPLES](LANGGRAPH_DESIGN_PRINCIPLES.md) | 历史框架比较与设计取舍；其它框架 API 未在本次重新核对 |
| [VIDEO_PROJECTS_ANALYSIS](VIDEO_PROJECTS_ANALYSIS.md) | 视频项目参考分析；不代表 Hermes 本地实现 |
| [HERMES_ATLAS_TRENDING](HERMES_ATLAS_TRENDING.md) | 历史生态热度材料；不作当前星数/排名依据 |
| [WORKSPACE_VS_WEBUI](WORKSPACE_VS_WEBUI.md) | 历史产品体验与链路比较；不是当前实测推荐 |
| [VERSION_HISTORY](VERSION_HISTORY.md) | 历史版本矩阵；旧“未发版”已限定快照日期 |
| [DOC_MAINTENANCE](DOC_MAINTENANCE.md) | 当前维护规范与旧文档组织演变 |
| [REVIEW_AND_CHANGES](REVIEW_AND_CHANGES.md) | 本轮逐篇范围、错误更正、源码入口及校验结果 |

<a id="questions"></a>
<a id="8-按问题找答案"></a>
<a id="section-8"></a>
## 8. 按问题找答案

| 我想知道 | 直接入口 |
|---|---|
| 内存 messages 能原样发给大模型吗？ | [工作集与请求投影](CURRENT_IMPLEMENTATION.md#current-messages) |
| 重启后怎样从 DB 恢复？ | [恢复链路](CURRENT_IMPLEMENTATION.md#current-restore) |
| 没压缩时怎样 flush？压缩后又怎样？ | [普通 flush](CURRENT_IMPLEMENTATION.md#current-flush) / [压缩提交](CURRENT_IMPLEMENTATION.md#current-compaction) |
| 轻量压缩是否也改 DB？ | [压缩机制区分](CURRENT_IMPLEMENTATION.md#current-compaction) |
| 外部缓存和插件 context 放在哪？有没有围栏？ | [context 组装示例](CURRENT_IMPLEMENTATION.md#current-context) |
| steer 三处处理是不是同一种消息？ | [steer 当轮注入与补发](CURRENT_IMPLEMENTATION.md#current-steer) |
| built-in memory 是不是每个 Topic 独立？ | [记忆与 Session 边界](CURRENT_IMPLEMENTATION.md#current-extensions) |
| 看板的真调度类和生命周期是什么？ | [Kanban 模块与时序](CURRENT_IMPLEMENTATION.md#current-kanban) |
| 人确认以后恢复了什么现场？ | [审批等待与继续](CURRENT_IMPLEMENTATION.md#current-approval) |

<a id="maintenance"></a>
<a id="9-归档与现行分卷的关系"></a>
<a id="section-9"></a>
## 9. 归档与现行分卷的关系

- [现行分卷目录](../../volumes/README.md) 是按设计主题组织的正文；这里保留单篇教程的解释深度与历史脉络。
- 两套文件**不再自动互相覆盖**。修改这里不会自动更新分卷；需要同步的结论应人工审阅后分别修改。
- 不要运行旧 README 所建议的“改 legacy → build_volumes → 覆盖所有卷”的日常流程。构建器仅保留早期合卷用途。
- 已删除的 Gateway 附录不在本轮恢复；旧链接已转到现行卷六。总映射见 [CATALOG](../../CATALOG.md)。

<!-- 旧版入口兼容 -->
<a id="appendices"></a>
<a id="与合订本章节对照"></a>
<a id="合并前单篇文档归档"></a>
<a id="如何改文档"></a>

<!-- 旧目录与迁移章节锚点兼容；完整内容入口见文首目录及主题迁移表。 -->
<a id="reading-routes"></a>
