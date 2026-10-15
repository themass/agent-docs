# 本轮设计文档增补总结

> 依据本地源码快照 `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd`；不宣称远端最新。目标是补上后端、运行支撑与生命周期，而不是重写旧文或用目录清点冒充全模块深潜。

## 目录

- [1. 改动结论](#change-results)
- [2. 新增与扩写清单](#change-files)
- [3. 验收与保全](#change-checks)
- [4. 仍待补齐](#change-next)

<a id="change-results"></a>
## 1. 改动结论

原书主要讲清了主循环、上下文、Surface 和 Gateway，但读者仍容易在**状态所有权、后端切换、退出清理、重启恢复、交付确认**上断链。本轮把这些隐含机制单独展开：

1. **模型后端不是一个配置名**：声明、协议转换、实际 client/route、账号池各自承担不同责任；fallback 要重绑运行时并重新做窗口检查。
2. **终端不是永久 shell**：按调用启动 shell、初始化快照、cwd 连续性、环境隔离与资源退出分别解释。
3. **任务成功不等于通知成功**：Job、时间槽、execution 和 delivery 分开；不确定的发送不能盲目重放。
4. **装好包不等于当前插件已生效**：worker、暂存、验证、选中版本发布、配置快照/journal/receipt 是另一套事务。
5. **注册与卸载有所有权**：profile scope、注册代际与任意卸载顺序决定是否能安全替换。
6. **多 Agent 有多种机制**：delegate、public lifecycle、Kanban、MoA 不混讲，进程内 handle 不当成跨重启凭证。
7. **日志、监控和持久账本不是一回事**；profile 的秘密查找也不能无条件回退全局环境。

正文增加了架构图、类图、时序图、流程图与状态图；图旁说明边的含义，并加入带中文注释的源码摘录/解释性伪代码、分支解读与排障入口。各新增专卷均有目录和总结。

<a id="change-files"></a>
## 2. 新增与扩写清单

### 新增四个专卷

| 文件 | 内容 |
|---|---|
| [10 模型后端与恢复](10-model-backends-and-resilience.md) | Transport/响应类型、凭据池、错误分流、fallback、辅助 LLM、协议回放 |
| [11 终端执行后端](11-terminal-execution-backends.md) | 执行计划/工厂、shell/cwd、主机/容器/远端边界、guard、前后台、退出竞争窗口 |
| [12 自动化与包运行时](12-automation-and-package-runtime.md) | tick、执行账本、owner 身份、交付 unknown/幂等 tombstone、PM 安装与发布事务 |
| [13 配置、秘密与观测](13-config-secrets-and-observability.md) | home/profile 归属、secret scope、bootstrap/platform 与安装职责、日志/monitoring/账本 |

### 保留原文增补，没有删除或改写旧段落

- [卷三 §4.7–4.10](03-runtime-session-and-loop.md#sec-4-lightweight)：按后续提问补充轻量整理、消息投影与 DB 原子提交；原第4章内容仍保留，仅在第5章前插入新节并增补目录。
- [卷五 §7](05-capabilities-extensions.md#cap-plugin-lifecycle)：插件能力与注册生命周期。
- [卷七 §6](07-multi-agent-and-kanban.md#multi-runtime-boundaries)：多 Agent 运行时边界。
- [卷一增补](01-platform-and-architecture.md#source-supplement)：完整系统责任地图、状态存放位置与深读入口。
- [卷九增补](09-reference-history-and-versions.md#source-supplement)：源码快照与现行增量维护。
- [MANIFEST 增补](MANIFEST.md#source-supplement)：四个新卷与覆盖等级。
- docs 的 [README](../README.md#source-supplement)、[CATALOG](../CATALOG.md#source-supplement)、[HERMES](../HERMES.md#source-supplement)：连接现行入口，明确早期“仅合卷/重建”说明不再适用于手写扩写。

### 新增阅读、审计与维护材料

- [分卷 README](README.md)：十三卷全书大纲、三条阅读路线、按问题定位。
- [VOLUME_STANDARD](VOLUME_STANDARD.md)：补齐缺失的写作标准，区分证据等级与图形/文本验收。
- [SOURCE_AUDIT](SOURCE_AUDIT.md)：模块族地图、已补专题与仍待补齐的优先级清单。
- [SOURCE_INVENTORY](SOURCE_INVENTORY.json)：5389 个受 Git 管理的代码文件，路径/hash/行数及 Python AST 符号；默认 L0。
- [SOURCE_EVIDENCE](SOURCE_EVIDENCE.json)：103 条新增专题的精确源码符号引用，关联本地提交、文件 hash 和定位行号。
- `hermes/docs/_merge/audit_source.py`：不 import 应用的清点/引用检查工具。
- `hermes/docs/_merge/verify_volumes.py`：新增片段的链接、锚点、代码围栏及可选原文前缀保全检查。
- `hermes/docs/_merge/test_document_audit.py`：审计工具的离线回归测试，不运行 Hermes。

<a id="change-checks"></a>
## 3. 验收与保全

本轮检查结果：

| 检查 | 结果 | 实际验证范围 |
|---|---|---|
| 源码清单与引用一致性 | 通过：5389 个代码文件、103 条精确符号引用 | 当前受控文件/hash/AST 符号与清单一致；不是逐行审计 |
| 新增文本结构 | 通过：18 份新文/增补片段，33 个 Mermaid 代码块 | 本地链接/锚点可解析、围栏闭合；未做 Mermaid 渲染 |
| 原文保全 | 前次 74 文档检查通过；本次旧基线有差异 | 本次卷三新增内容可单独剥离并逐字节恢复编辑前版本；旧基线差异详见文末，不回退其他编辑 |
| 审计工具回归测试 | 通过：13 项 | 文件角色、AST 符号、JSON、围栏、链接/锚点、保全成功/失败场景 |
| Hermes 运行时测试 | 未执行 | 阅读部分测试断言，不把它计为实测 |

维护命令如下（从 docs 仓库根执行）：

```sh
python3 hermes/docs/_merge/audit_source.py --check
python3 hermes/docs/_merge/verify_volumes.py
python3 -m unittest discover -s hermes/docs/_merge -p 'test_document_audit.py' -v
```

本轮编辑前另保存了 74 个既有 Markdown 文件，以原文保全检查确认旧正文未改（卷三后续允许两处有界插入）；不把仓库本来已有的删除/重命名算作本轮改动。未运行旧合卷脚本、未修改 Hermes 源码、未安装依赖、未提交或重置用户改动。

**验收边界**：上述机械检查不覆盖所有旧文的历史链接，不校验 Mermaid 语法或视觉排版，不证明每张图边都等于实际调用；未执行 Hermes 运行时/端到端测试。测试源码阅读与符号检查不能代替实测。

<a id="change-next"></a>
## 4. 仍待补齐

本轮不是“所有模块已完全掌握”的终点。[审计后续清单](SOURCE_AUDIT.md#audit-next) 已按 P1–P3 排序：CLI 命令契约、浏览器/媒体供应商完整链、Dashboard/Desktop 页面/API、IM adapter 差异、rooms/relay、Cron 周边、构建发布、Skill 配方和 eval 数据契约仍需逐专题深潜。

建议下一批先扩写 **CLI 配置/身份全链 → Browser/媒体能力 → 前端页面与 API 对照**；每批补齐输入输出、状态所有者、失败/取消/重启与测试场景，再更新覆盖等级，不仅新增类名或文件名。


## 后续专题增补：卷三第4章的轻量整理与消息存储

用户后续要求直接完善第4章，因此本批不是另建文件，而是在原 4.6 之后补入 4.7–4.10，并添加目录项：

- 区分完整压缩内预处理、独立主动整理和 API-only 投影；注明默认开关、收益/rearm、缓存与失败门槛。
- 解释 DB 行 → 内存工作历史 → API 请求副本 → Transport/SDK payload 的数据链与 `api_content`。
- 走读完整提交和轻量提交的不同边界，说明 coverage/watermark/租约、原文归档、尾部搬运与并发消息保留。
- 新增 3 张机制图、带注释源码/SQL、逐行示例，以及 19 条精确符号引用；总引用由 44 增至 63。
- 标记源码 docstring 与函数体在“是否截断工具参数”上的不一致，按当前函数体解释，未修改源码。
- 目录/章节增补均有成对标记；验证脚本只允许卷三这两个限定区域插入，新增 2 项回归测试，确保其他旧字节仍按原顺序保留。

本批仍未执行 Hermes 运行场景或 Mermaid 渲染；文本检查、源码引用核对和 13 项工具测试通过，不推导为运行验证通过。

## 后续专题增补：工作消息对象与三条持久化主链

在卷三第4章继续追加 §4.11–4.15，原有正文和上次补充均保留：

- 工作对象：分清调用方 history、本轮 messages、请求副本与 DB 行，解释浅拷贝和四种身份。
- 重启恢复：以 CLI 早期恢复为主线，说明模型/展示双历史、active 过滤、反序列化、已持久化标记、轮首建上下文及租约等待后的刷新。
- 普通 flush：解释 collect → 行投影 → 批次事务 → 回填内存身份/标记，以及工具前、正常答复、finalizer 多处持久化边界。
- 压缩交接：说明候选、DB 提交、内存切换三个阶段，区分原地/轮换/独立轻量整理的基线交接，避免压缩后重复写入。
- 补充发送投影、结果回交、崩溃恢复、隔离 fork 与外部副作用的不确定性。
- 新增 4 张 Mermaid 图、字段表、时刻表与带注释算法，新增 18 条精确引用，总计 81 条；结构检查与 13 项工具测试通过，未做运行时/渲染验证。

**保全结果更正/限定**：上表 74 文档保全通过是前次验收结果，不是本次重跑结论。本次旧基线检查发现卷一、MANIFEST、卷三存在历史基线外变化；卷三编辑前已存在差异，本次未修改另外两份文件。仅剥离本次卷三两处插入后，与本次编辑前副本逐字节相同；不回退其他编辑，也不改变旧基线或放宽脚本。

## 后续专题增补：外部 Memory 与插件 context 的注入位置

卷三追加 §4.16 和目录入口，保留原正文，明确：

- Memory 内容由宿主包装为 `<memory-context>`，插件 context 默认在标签外。
- 字符串路径保留原始 content，但向同一个 live message 写入完整 api_content；多模态直接追加 live content 的 text part。
- 通过注入前、工作消息、实际请求三个示例，解释侧车不是 API 字段，以及持久化和历史回放的作用。
- 标明超长 hook spill、MoA / codex_app_server 分支和后续 Context Engine 替换的边界。
- 新增一张流程图与源码入口，当前精确引用总数 90；结构检查共 32 个 Mermaid 围栏，13 项审计工具测试通过。

本次仅删除两处新增插入即可逐字节还原本次编辑前卷三，未修改旧正文；不将此等同于旧 74 文档基线全部通过。未做运行时或 Mermaid 渲染验证。

## 后续修订：卷四从作者分类改为读者可检索的导航

- 不再用“澄清 / E2E / 权威表 / 边界”作为读者看到的主题摘要；卷名与 30 个正文标题改为具体内容/问题，原节号保留。
- 卷首先说明全卷回答什么，再提供 14 个常见问题的直达表、三条阅读路线及展开到小节的完整目录；链接到卷三新补的消息恢复与 context 实例。
- 旧标题对应的锚点显式保留，正文段落、表格、图及代码不删改；追加一条范围说明，防止旧注入简表被误读为“不进内存、不落库”。
- 对卷四整篇检查本地链接、旧锚点兼容与围栏；逐字比较确认，除标题/导航和新增范围说明外，原正文内容保持不变。这里是本次编辑前副本的保全检查，不是旧 74 文档基线全部通过。
- 本次为信息架构修订，不代表新增的运行时场景验证；未执行 Hermes 或 Mermaid 渲染。

## 后续专题增补：Steer 的三处交付出口

- 卷四新增 §4.10、问题直达与目录项：入 pending 槽位、工具批次后追加、请求前定位插入、finalizer 转交下一轮。
- 明确前两个成功出口调用 steer_user_row，第三个仅返回原始文本，不自动添加标记或 display_kind。补消息实例、流程图、持久化条件、system 通道说明与 redirect 分支边界。
- 纳入源码审计后共 103 条精确引用；18 份新增片段、33 个 Mermaid 围栏检查通过，13 项工具测试通过。本次卷四插入可完整剥离，恢复编辑前内容；未改旧正文、未做运行时或图形渲染验证。

## 后续修订：卷五三份文档的主题导航与内容层级

- 主卷明确为“工具与扩展”，附录 A 明确为“Memory 使用与 Provider 接入”，附录 B 明确为“Memory 协作与经验沉淀”；三份卷首先提供选篇表、按问题查找、阅读路线和分层完整目录。
- 主卷将“先澄清 / 谁调用谁 / 权威表”等标题改成可检索的工具启用链、工具调用执行链、模块机制与插件生命周期；原 §4.6 内置工具清单正文整体移到 §4.5 后，修复章节顺序。
- 附录 A 统一使用指南与 Provider 部分的层级编号，展开操作目标、写入动作、容量、更新时机、各 Provider 的存储/写入/读取、配置、自定义接入与排障入口。
- 附录 B 修复 Skills 下混入多个独立主题的层级：Telemetry、Curator 生命周期、Trajectory 与 Curator Review 独立成节，分别展开下级内容；消除旧 C/D/E/E 与小节跳号造成的定位歧义。
- 保留全部旧标题锚点，修复两处原有失效链接（主卷的 Surface callback 表、附录 A 的 Frozen Snapshot 引用）。除标题、导航与这两处链接外，原正文非空行多重集保持一致，包括代码和图；仅上述主卷工具清单改变位置。此为本次编辑前副本的检查，不替代旧 74 文档基线验收。
- 三份全文的本地链接、旧锚点兼容、显式锚点唯一性及围栏检查通过；全卷结构检查仍为 18 份新增片段、33 个 Mermaid 围栏，源码审计仍为 103 条精确引用，13 项文档审计工具测试通过。本次只调整信息架构，未执行 Hermes 运行时或 Mermaid 渲染验证。

## 后续专题增补：built-in memory 的定义与使用链路

- 卷五附录 A 新增 §1.0 与五个子节，并接入问题导航和完整目录：定义两份长期笔记、文件位置与容量，区分 live entries 和冻结的提示词快照。
- 补充磁盘 → MemoryStore → system prompt 的读取链路，以及模型 → memory 工具 → live store → 文件的写入实例；新增流程图、时序图和状态对照表。
- 解释 built-in memory、工作 messages、SessionDB、外部 Provider、Skills、插件 context 的区别，以及为何内置笔记不走外部召回的 `<memory-context>` 包装。
- 保留原 §1.7–1.8，追加适用条件：普通写入不即时刷新快照，但压缩后 invalidate_system_prompt 重新加载是当前会话内的刷新入口；不能绝对理解为只在下一次会话生效。
- 本次附录全文本地链接与围栏检查通过，git diff 空白检查、13 项文档审计工具测试及既有源码引用审计通过；新增符号入口来自本次本地源码阅读，未扩充机器引用清单。既有增补扫描仍报告 18 份片段 / 33 个 Mermaid 围栏，不含本次附录新增的 2 张图；未做 Mermaid 渲染或 Hermes 运行时验证。

## 后续专题增补：Channel 独立模块的架构与四条生命周期链路

- 卷六第2章追加 §2.1–2.7，卷首增加按问题查找和小节目录；区分 Channel 适配层、具体平台频道、Gateway 编排与外部平台服务。
- 新增整体架构图、核心类图，以及启动、停止、入站、出站四张时序图，共 6 张图。以真实 SignalAdapter 展示继承与连接资源，不把所有平台假设成同一种协议。
- 启动解释注册表/内置工厂优先级、先装配后连接、有界并发、失败清理、degraded 状态与 Profile 隔离；停止解释唯一 stop task、先 drain 后 teardown、取消任务再断连、DB 关闭顺序与超时兜底。
- 入站解释 MessageEvent / SessionSource、创建 task 前同步占 guard、Adapter/Runner 双守卫、控制消息 inline 与 pending/debounce；出站解释普通回复由 Base 生命周期交付、发送前登记义务、SendResult 与重连后的 transport 所有权。
- 保留第2/4章旧简图，追加说明其省略与顺序限制；明确流式、媒体、审批、cron 主动出站不应套用普通最终文本的同一路径。
- 保全检查：剥离两个新增标记区域及新增目录行后，可逐字节还原本次编辑前卷六；旧锚点保留、显式锚点无重复，未增加坏链接。全文原有两处指向同一缺失比较文档的链接仍存在，本次未修改。
- 本地 AST 静态解析核对 28 个源码符号，无需导入 Hermes。既有全卷结构检查、103 条机器清单引用及 13 项审计工具测试通过；既有结构扫描的 18 片段 / 33 围栏不含本次卷六增补，本次另检新增 6 个图围栏闭合。未执行平台连接、收发/启停场景或 Mermaid 渲染，不将静态核对当作运行验证。

## 后续专题增补：Follow-up 队列与 Channel 领域能力清单

- 卷六新增 §2.8，解释 Adapter pending 头槽、`SessionState.conversation.queued_events` FIFO 溢出链、Runner 内消费的 queued follow-up 与 steer 的边界；补充入队、提升、递归下一轮、Hook、递归深度上限、照片 burst 合并和队列上限。
- 新增 follow-up 消费时序图与关机/重启恢复流程图：说明当前轮如何复用更新后的 history，为什么不重新伪装成平台 callback，以及 shutdown spool → 启动 replay 到 DB 与独立 auto-resume 的区别。
- 新增 §2.9 Channel/Gateway 能力清单，覆盖注册/探测、事件规范化、访问控制、并发/忙时、Agent 交接、可靠出站、HITL 控制、恢复、主动事件和扩展观测，作为后续平台适配器检查清单。
- 原有正文、上一轮 Channel 增补、旧锚点均保留；剥离本轮导航和标记区域后恢复本轮编辑前文档。既有两处比较文档缺失链接未修改。新增 2 张图围栏闭合，未做 Mermaid 渲染、真实平台队列或重启运行验证。

## 后续修订：Channel 图统一真实实体与方法归属

- 重绘 §2.1 整体架构、§2.2 类图及启动/停止/收/发/follow-up 五张时序图：统一使用 `runner: GatewayRunner`、`adapter: SignalAdapter`、`turn_runner: TurnRunner` 等实例与真实类型；用 Signal 展开实际协议方法。
- 类图展开本专题相关 Mixin 继承、对象持有与调用依赖，补入 TurnContext、SessionState/ConversationState、入站信封与回执。新增实体—源码—职责对照表和图例。
- 修正 follow-up 方法归属：`_run_agent_queued_followup` / `_run_agent_drain_pending` 定义于 GatewayTurnMixin，不属于 TurnRunner；Mixin 不是独立实例，Adapter 基类和子类也不是两个运行服务。ledger 明确为模块函数，外部 Signal 服务不伪装为 Python 类。
- 保留旧章节锚点及原始概览图，并注明历史简图与实体级图的层次区别。全文围栏、旧锚点兼容及无新增坏链接检查通过；10 项 AST 方法归属核对及 13 项文档审计测试通过。原有缺失比较文档链接仍存在；未进行 Mermaid 渲染或平台运行验证。


## 2026-10-15 · 卷八校验规则与人工审批现场补充

- 将卷八导航改为按问题检索：校验链、硬拒绝/问人规则、CLI/IM 等待、ID 关联、失败与重启、写入暂存审核分别直达，保留旧章节与锚点。
- 依据本地源码补齐 §0.3–0.4 安全控制矩阵、Skill 来源/verdict 策略和 context 扫描例外；§2.7–2.16 展开完整 terminal 调用链、规则优先级、真实类/状态所有权、CLI Queue 与 Gateway Event 时序。
- 明确 tool_call_id、session_key、request_id、pattern_key 与平台卡片 ID 的差别，补充 FIFO/精确选择、并发合并、timeout 与 resolver 结算竞态。
- 增加一条说明用的完整 terminal 请求示例：模型请求 → 校验 → 人工确认 → 同栈执行 → 原 tool result → 后续推理；示例命令未执行。
- 区分在线等待与 memory/skills 文件 staging：后者重新加载 payload 并应用，不是恢复旧 Agent 调用栈；同时补充拒绝、无 UI、取消与进程重启边界。
- 校正旧文将 check_dangerous_command 当作完整 terminal 入口、所有审批都经 _run_approval_gate、忽略容器分支用户 deny 等表述，并更新 CLI/Gateway 方法的实际文件归属与卷五旧跳转。
- 本次仅修改文档；全文链接/旧锚点、源码符号与既有文档审计检查另行核验，不将静态检查宣称为 Mermaid 渲染或 Hermes 运行时验证。

## 2026-10-15 · 卷七 Kanban 整体架构与任务全生命周期补充

- 将卷七导航改为按实际问题检索，保留旧章节及锚点；展开第4节为 §4.1–4.17，覆盖架构分层、真实实体、数据模型、状态/依赖、拆解/Swarm、Gateway 启停、调度/并发、原子认领、worker 上下文、工作区/成果、完成/阻塞、review/返工、恢复、通知/wake、Dashboard 和运维清单。
- 以本地源码快照 `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd` 为口径，补充10张架构/类/ER/状态/流程/时序图（替换旧1张简图，全文净增9张）。类、模块、Mixin 和运行实例明确区分，不再把 dispatch_once 当作数据库服务。
- 修正“worker exit code 更新任务即完成”的误导：成功需要显式领域结算；说明 Task / Run / claim / PID 指纹 / SessionDB 各自职责、CAS 与 expected_run_id 防旧写回、失败后新尝试与原地 turn 重试的区别。
- 解释 triage 拆解与 Swarm 的根任务依赖方向、max_spawn 是本板 live 并发额度、主机并发/资源压力门禁、scheduled 当前不自带定时唤醒、unblock 可恢复 review 阶段等边界。
- 增加一条“接口实现 → 审核返工 → 再实现 → 通过 → 后继派工/结果交付”的完整示例及带注释认领 SQL；示例不执行、不冒充正式工具 schema。
- 区分看板持久 review 与卷八同栈安全审批；区分 Dashboard WebSocket、被动通知与 wake，说明 ping checkpoint/事件游标及外部交付非 exactly-once，不能等同旧 Agent restore。
- 保留第0–3节及第5–8节正文；修复原导航指向 delegate 标题的坏锚点。全文链接、旧锚点保留、围栏及源码符号另行静态核对；既有审计工具不覆盖全部本次增补，未将其通过等同 Mermaid 渲染或 Hermes 运行验证。
- 核验结果：本次另检卷七全文链接、全部旧锚点、显式 ID 唯一及15个 Mermaid 围栏闭合（第4节10个）；对照本轮编辑前快照，其他章节正文保持，仅为 delegate 目录补稳定显式锚点。75个源码符号静态核对、10项方法归属与 GatewayRunner 继承核对通过。既有全卷结构检查、103条机器清单源码引用和13项审计工具测试通过；未执行 Mermaid 渲染、真实派工/审核/通知或重启场景。
