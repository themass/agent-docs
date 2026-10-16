# Legacy 文档校订记录

> 日期：2026-10-15 · 源码基线：`/Users/gqli/work/deepagents/hermes-dev/hermes-agent` commit `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd`。

<a id="1-本轮做了什么"></a>
<a id="section-1"></a>

<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 本轮做了什么](#section-1)
- [2. 已明确修正的事实](#section-2)
- [3. 逐篇状态与边界](#section-3)
  - [3.1 原文件逐篇处理清单](#section-3-1)
- [4. 校验结果](#section-4)
- [5. 后续维护建议](#section-5)
- [6. 目录与主题归属整理（2026-10-15）](#section-6)
<!-- visible-toc:end -->

## 1. 本轮做了什么

本轮不是把旧 25 篇文档全部重写成新卷，而是采取“**保留清晰叙事 + 在错误位置校正 + 新增当前链路导读**”的方式：

- 新增 [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md)：用真实模块/函数串起系统边界、工作区消息、重启恢复、普通 flush、压缩、context、steer、delegate、Kanban、审批和扩展边界。
- 重写 [README.md](README.md)：按阅读路线、问题入口和六个主题部分组织，不再让读者从无意义的文件清单猜内容。
- 重写 [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md) 的当前维护规则，明确 legacy 与手写 volumes 不自动互相覆盖。
- 在原章节中修正关键错误，保留长篇图表/设计推理，并加入校订入口和适用范围。
- 对 25 个旧文档增加文首导航、源码基线、适用范围和现行卷链接；旧版本标签保留为历史身份，不冒充当前版本。
- 修正可明确定位的本地链接；示例包内路径和未随仓库提供的外部参考改成历史引用说明。
- 更新 `hermes/docs/CATALOG.md` 与 `_merge/README.md` 的矛盾维护指引，避免旧构建器覆盖手工增补。

<a id="2-已明确修正的事实"></a>
<a id="section-2"></a>
## 2. 已明确修正的事实

| 主题 | 旧稿容易造成的结论 | 当前校订结论 | 关键源码入口 |
|---|---|---|---|
| 工作区 message | 内存 message 可以原样送 API | 工作集、SessionDB 行和 API 请求投影是三层；`build_api_messages` 会消费 sidecar/内部字段 | `agent/turn_context.py`, `turn_request_assembly.py`, `chat_completion_helpers.py` |
| 普通 flush | 每轮全量重写历史 | `_flush_messages_to_session_db_unlocked` 做增量收集与写入，并维护持久化身份 | `agent/session_persistence.py` |
| 压缩 | 轻量裁剪必然先跑；超 token 后必然 LLM | 独立 tool-result prune 是 opt-in；完整压缩有自己的准备、真实 usage、锁/租约和回退条件 | `agent/context_compressor.py`, `agent/turn_preflight.py` |
| 压缩 DB | 所有旧行都 `active=0, compacted=1` | 摘要覆盖的旧行通常如此；原样携带/并发尾部的旧副本可 `active=0, compacted=0` | `agent/conversation_compression.py`, `hermes_state_messages.py` |
| 外部 context | 插件 context 一定在 memory fence 内，或完全 ephemeral 不落库 | `<memory-context>` 只由外部 memory prefetch 构造；插件文本在围栏外；字符串 user 的组合版本可在 `api_content` sidecar 持久化 | `agent/turn_context.py`, `agent/session_persistence.py` |
| pre_llm_call | 每次 ReAct API 都调用 | 当前 turn-context 调用按 `turn_context.py` 生命周期，不应抽象成每次模型迭代必调 | `agent/turn_context.py` |
| steer | 两个点把文本改到 tool.content，且永不新增 user | pre-API 和 post-tool 都追加独立 user 行；收尾仍有 pending 则交回入口安排后续 turn | `turn_iteration_prep.py`, `agent_runtime_helpers.py`, `turn_finalizer.py`, `gateway/run_turn.py` |
| 子代理预算 | 默认 90/50 或共享父 budget | AIAgent 构造默认 `sys.maxsize`；delegate 默认常量 250；当前 child 传 `iteration_budget=None` 创建独立对象 | `tools/delegate_tool.py`, `agent/agent_init.py`, `agent/iteration_budget.py` |
| Kanban | 一个 Dispatcher 类、`max_spawn` 全局、scheduled 自动唤醒 | Gateway mixin + `_KanbanDispatcher` + `dispatch_once`；`max_spawn` 为 board live cap，host cap 另算；scheduled 不等于已有定时唤醒器 | `gateway/kanban_watchers*.py`, `hermes_cli/kanban_db_dispatch.py` |
| 审批 | `check_dangerous_command` / `_run_approval_gate` 是完整且唯一入口 | terminal 完整入口是 `check_all_command_guards`；用户 deny 仍在容器豁免分支先检查；插件/其它审批有不同入口 | `tools/approval.py`, `tools/approval_gateway_wait.py`, `hermes_cli/cli_modal_mixin.py` |
| Telegram Topic | Topic 就是 Kanban、每 Topic 独立 memory/完全隔离 | `TelegramAdapter` 负责 topic/session 路由；Session 历史可分开，但 Profile memory 与 OS/文件隔离不能据此推出 | `plugins/platforms/telegram/adapter.py` |
| 大结果阈值 | 50KB 是默认当前阈值 | 旧表述已改为 `DEFAULT_RESULT_SIZE_CHARS=100_000` 的源码锚点 | `tools/budget_config.py`, `TOOLS_SYSTEM.md` |

<a id="3-逐篇状态与边界"></a>
<a id="section-3"></a>
## 3. 逐篇状态与边界

| 文件组 | 状态 | 未做的事 |
|---|---|---|
| 架构/运行时/状态/Prompt | 重点链路校订 | 未逐行重写所有历史示例、旧行号和每个 Provider 分支 |
| Tools/Skills/MCP/Plugins/Memory | 目录与关键边界校订 | 未枚举当前所有注册项、插件 hook 全表和每个外部 Provider |
| Gateway/Telegram/HITL/Security | 关键入口和等待/规则校订 | 未通过运行时逐个平台实测；旧命令矩阵不自动代表全部平台 |
| Multi-agent/Kanban | 预算、真实调度实体、容量与状态语义校订 | 未把全部 Kanban schema、repair、通知/重试边界逐段重写 |
| LangGraph/Video/Atlas/Workspace | 明确标为历史参考 | 未联网查最新外部项目、星数、性能或产品能力 |
| Version/maintenance | 日期和维护操作校订 | 未把旧版本表重新核验为远端发布清单 |

<a id="31-原文件逐篇处理清单"></a>
<a id="section-3-1"></a>
### 3.1 原文件逐篇处理清单

| 原文件 | 本次处理 / 保留边界 |
|---|---|
| [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) | 重写 steer 三个消费边界，纠正共享预算，补充轻量压缩和 context 持久化。 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 校正父/子预算默认值；保留设计原则、模块地图及旧源码导读。 |
| [CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md) | 修复已合并/删除入口链接；当前 channel 生命周期与 followup 详见卷六，旧长代码保留为教程。 |
| [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md) | 废止 legacy 自动覆盖分卷的操作建议，旧地图和规模表降为历史记录。 |
| [EXECUTION_FLOW_ANALYSIS.md](EXECUTION_FLOW_ANALYSIS.md) | 保留旧长链路与代码样例；旧内联源码、行号和运行参数未逐段认证，请结合当前链路阅读。 |
| [HERMES_ATLAS_TRENDING.md](HERMES_ATLAS_TRENDING.md) | 历史社区资料，不作为当前版本、实现完整性或产品性能证据。 |
| [HITL_APPROVAL_FLOW.md](HITL_APPROVAL_FLOW.md) | 校正完整 guard 入口、容器/deny 顺序、CLI 方法位置和唯一闸门说法；保留 Queue/Event 教学。 |
| [KANBAN_MULTIAGENT_DEEP_ANALYSIS.md](KANBAN_MULTIAGENT_DEEP_ANALYSIS.md) | 校正 watcher 实体、并发帽和 scheduled 语义，标注历史调度伪代码；完整 Schema/全部算法摘录未逐行重写。 |
| [LANGGRAPH_DESIGN_PRINCIPLES.md](LANGGRAPH_DESIGN_PRINCIPLES.md) | 作为历史设计对比，不将其它框架行为视为 Hermes 实现；本次未核验外部最新 API。 |
| [MCP_INTEGRATION.md](MCP_INTEGRATION.md) | 修复 OAuth 目录定位；协议能力、Hermes 已实现子集及历史示例不能混称为完整支持。 |
| [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) | 明确 Profile memory、Session Search、外部 Provider 与压缩的边界；旧适配器代码未全量复核。 |
| [MULTI_AGENT_ARCHITECTURE.md](MULTI_AGENT_ARCHITECTURE.md) | 校正独立预算、构造默认与 delegation 的 250 默认；旧性能/token 数仅为样例。 |
| [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md) | 修正 pre_llm_call sidecar 的持久化说明；静态 Hook 表以源码 VALID_HOOKS 为准。 |
| [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md) | 校正真实拼装顺序、插件围栏范围和 api_content 持久化；旧完整 Prompt 层数不是永久协议。 |
| [SECURITY_SCAN_DEEP_ANALYSIS.md](SECURITY_SCAN_DEEP_ANALYSIS.md) | 增加当前命令 guard 导航与适用范围；旧 scanner 正则、信任名单、行号未全量重新认证。 |
| [SKILLS_SYSTEM.md](SKILLS_SYSTEM.md) | 修复目录跳转；保留层次化解释，旧外部仓库/命令/安全扫描例未全部重新验证。 |
| [STATE_AND_AUXILIARY.md](STATE_AND_AUXILIARY.md) | 增加 DB→工作集、普通 flush、压缩提交三条链路及状态差异。 |
| [SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md) | 保留单次运行样本；时间、路径、模型和字节不代表当前每次调用。 |
| [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) | 保留模块视角并补齐章节导航；UI 私有事件、版本和全部路径未作运行验证。 |
| [TELEGRAM_MULTISSESSION_TOPICS.md](TELEGRAM_MULTISSESSION_TOPICS.md) | 纠正 Topic=看板、独立记忆/完全隔离表述；更新插件路径；外部协议年代与全部命令行为未重测。 |
| [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) | 修正旧 50KB 阈值表述；全部工具列表和示例实现不视为当前 API 合约。 |
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | 旧未发版章节限定为 2026-07-22 快照；未联网重新核验发布矩阵。 |
| [VIDEO_PROJECTS_ANALYSIS.md](VIDEO_PROJECTS_ANALYSIS.md) | 保留历史参考项目分析；项目热度、产品能力、实测性能未重新核验。 |
| [WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md) | 将开头推荐限定为历史判断；旧轮询间隔、接口与星数未重测，不再当作当前选择建议。 |
| [README.md](README.md) | 按阅读路线、六个主题部分和实际问题重组总目录；保留与现行分卷的双向关系。 |

<a id="4-校验结果"></a>
<a id="section-4"></a>
## 4. 校验结果

已完成：

- 编辑前 25 个 legacy 文件快照保存在 `/tmp/hermes-legacy-before-20261015`。新增 2 篇后，共检查 **27 个 Markdown 文件**，围栏全部闭合，本地链接与锚点无错误，共 **140 个 Mermaid 块**（原 131 个；未通过渲染器验证）。
- 对 **30 个源码文件、50 个类/函数符号及 6 个方法所属类**进行了 AST 存在性检查，具体清单见 [SOURCE_REVIEW.json](SOURCE_REVIEW.json)。纠正了旧笔记中的 `initialize_agent` 误名，实际函数是 `agent_init.init_agent`。
- 旧章节锚点与编辑前快照对比无丢失；改名/重写章节的历史锚点保留兼容入口。目录只作为定位，不伪造运行证据。
- 本轮独立检查命令：`python3 hermes/docs/_merge/audit_legacy.py`。指定源码可用 `--source-root`；检查旧锚点保留可传 `--baseline /tmp/hermes-legacy-before-20261015`。
- 原有 `audit_source.py --check`、`verify_volumes.py` 和 **13 项文档审计单测**通过。它们只覆盖原定义的分卷审计片段；**不替代本次独立 legacy 检查，也不是所有历史代码摘录认证**。
- 没有运行旧合卷构建器、提交 Git、恢复已删除附录或改动 Hermes 源码；保留工作区其它已有修改。

尚未声称完成：

- 没有运行 Hermes 的完整端到端会话、真实 LLM、Telegram、Gateway、Kanban worker 或审批 UI。
- 没有用 Mermaid 渲染器验证图形布局；环境中没有 `mmdc`。
- 没有把源码行号当作稳定接口；旧行号仅在相应版本阅读时有价值。
- 没有使用网络把本地源码审计升级为“最新发布/外部产品比较”结论。

<a id="5-后续维护建议"></a>
<a id="section-5"></a>
## 5. 后续维护建议

新增设计时先修改 `CURRENT_IMPLEMENTATION.md` 或现行 `volumes/` 的对应主题，再在旧教程中补一个指向，而不是复制第三套事实。每次源码变更至少重新核对：消息投影/flush、压缩提交、steer、审批入口、Kanban dispatcher 和 Topic 路由这六个跨模块边界。

<a id="outline-topic-moves"></a>
<a id="目录与主题归属整理2026-10-15"></a>
<a id="section-6"></a>
## 6. 目录与主题归属整理（2026-10-15）

本次针对阅读结构单独调整：各篇使用展开的 `## 目录`，列出章与节；章节编号按实际层级连续生成。原有小节锚点保留，避免旧链接失效。长教程不再作为不相关文档的附录堆叠。

| 原位置 | 现在的完整设计位置 |
|---|---|
| `TOOLS_SYSTEM.md` · 11. 深潜：skill_manage | [skill_manage：技能写入、校验与管理](SKILLS_SYSTEM.md#skill-manage-design) |
| `TOOLS_SYSTEM.md` · 12. 深潜：session_search | [session_search：历史检索与辅助模型执行](MEMORY_SYSTEM.md#session-search-design) |
| `TOOLS_SYSTEM.md` · 13. 深潜：delegate_task | [delegate_task：创建、调度、执行与结果回收](MULTI_AGENT_ARCHITECTURE.md#delegate-task-design) |
| `AGENT_LOOP_ARCHITECTURE.md` · 5.5 安全与权限体系（12 维度纵深防御） | [纵深防御全景：Agent、工具与运行环境的检查边界](SECURITY_SCAN_DEEP_ANALYSIS.md#defense-boundaries) |
| `AGENT_LOOP_ARCHITECTURE.md` · 11. Plugin Hook 全表 | [Hook 生命周期全表：触发点、参数与可改变的行为](PLUGINS_SYSTEM.md#hook-lifecycle-table) |
| `AGENT_LOOP_ARCHITECTURE.md` · 5b. 主/子 Agent Prompt 区分机制 | [主代理与子代理的 Prompt 组装差异](PROMPT_SYSTEM_ARCHITECTURE.md#parent-child-prompt) |
| `AGENT_LOOP_ARCHITECTURE.md` · 13. 附录：跨框架选型（原 AIAgent §16） | [附录：Hermes 与图式框架的选型边界](LANGGRAPH_DESIGN_PRINCIPLES.md#framework-selection) |
| `SURFACE_ARCHITECTURE.md` · 8. 压缩与 Route 作用域（v0.19+ 稳定性） | [模型 Route 与压缩预算：切换模型后的窗口作用域](AGENT_LOOP_ARCHITECTURE.md#route-compaction-scope) |
| `MULTI_AGENT_ARCHITECTURE.md` · 14. 上下文压缩完整流程 | [历史压缩设计与现行链路对照（非当前执行合约）](AGENT_LOOP_ARCHITECTURE.md#historical-compaction-design) |
| `SECURITY_SCAN_DEEP_ANALYSIS.md` · Part B · Background Review（自进化审查）{#part-b-background-review} | [后台自进化：Background Review、skill_manage 与 Curator](SKILLS_SYSTEM.md#background-review-design) |

- 运行时篇把 Turn / Iteration 术语前置；状态篇把恢复、flush、压缩三条消息链路移到状态模型之后。
- 修复多 Agent 篇 Clarify 与 skill_manage 引用文件示例缺失的代码围栏，避免 Python 注释、字符串中的 Health Check / User Management 被误识别成章节。
- 迁移的是完整正文、代码与图表；原位置留下边界说明和链接，不删除设计内容。历史压缩示例单独标识为历史，不当作当前流程。
- 本轮只整理 legacy 单篇文档，不运行合卷构建器，不改写现行 volumes。

**本次结构验收结果**：27 篇均有唯一的可见目录，章/节目录与正文标题一致；本地链接可解析，重排前及上轮校订前的章节锚点兼容检查通过。重排前后均为 140 个 Mermaid 块，并按全目录图表内容多重集核对，迁移未丢图或改写图内容（仅忽略行尾空白）。新增 7 项目录回归测试，连同既有 13 项文档审计测试共 20 项通过；源码符号审计与分卷结构校验通过。未执行 Mermaid 渲染或 Hermes 运行测试。
