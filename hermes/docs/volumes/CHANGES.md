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
