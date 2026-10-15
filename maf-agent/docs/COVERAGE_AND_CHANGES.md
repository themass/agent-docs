# MAF 文档覆盖矩阵、缺口与改动清单

> 本文记录“已有文档讲了什么、源码实际还需要补什么、哪些是产品后端责任”。它不把未知误写成缺失，也不把框架能力误写成部署保证。

## 目录

- [1. 评审范围](#1-评审范围)
- [2. 源码证据索引](#2-源码证据索引)
- [3. 覆盖矩阵](#3-覆盖矩阵)
- [4. 真正缺口与建议](#4-真正缺口与建议)
- [5. 生产后端核对表](#5-生产后端核对表)
- [6. 验证与限制](#6-验证与限制)
- [7. 本轮文件改动](#7-本轮文件改动)

## 1. 评审范围

- 现有文档：`README.md`、`ARCHITECTURE.md`、`ARCHITECTURE_PART1.md`、`ARCHITECTURE_PART2.md`、`ARCHITECTURE_PART3.md`、`DESIGN_THINKING_SERIES.md`。
- 对照源码：Python core、harness、workflows、hosting、hosting-responses、ag-ui，以及 function-calling loop specification。
- 目标：增加架构厚度和后端可落地性；不修改 Agent Framework 业务源码。
- 基线：本地 `agent-framework` HEAD `056a0d4f50dc641c2cd0e7def94b694b2ead6e24`，Python `pyproject.toml` 版本 `1.21.0`。

## 2. 源码证据索引

| 证据 | 文件/符号 | 说明 |
|---|---|---|
| E1 | `core/.../_agents.py::RawAgent.run` | run identity、非流式/流式分支、解析和收尾 |
| E2 | `core/.../_agents.py::_prepare_session_and_messages` | provider before_run、历史分支、tools/instructions 合并 |
| E3 | `core/.../_sessions.py::AgentSession` | session id、service session、可序列化 state |
| E4 | `core/.../_sessions.py::SessionStore/FileSessionStore` | deep copy、原子替换、last-writer-wins 限制 |
| E5 | `core/.../_types.py::ResponseStream` | 消费、异常关闭、finalizer/result hooks |
| E6 | `core/.../_workflows/_runner.py::RunnerImpl` | superstep、commit/discard、checkpoint 时点 |
| E7 | `core/.../_workflows/_checkpoint.py` | lineage、graph signature、safe type/path validation |
| E8 | `core/.../_harness/_agent.py` | built-in providers/middleware/compaction 装配 |
| E9 | `core/.../_harness/_background_agents.py` | child session、并发 task、release/cancellation |
| E10 | `ag-ui/.../_approval_lifecycle.py` | approval occurrence 生命周期与 owner |
| E11 | `hosting/.../_state.py` | target resolution、session store、hosting 非职责 |
| E12 | `samples/04-hosting/af-hosting/local_responses/app.py` | 真正的 route、选项 allow-list、最终化后持久化 |
| E13 | `docs/specs/004-python-function-calling-loop.md` | 规范矩阵、已知 gap、验证命令 |

## 3. 覆盖矩阵

| 主题 | 原文覆盖 | 源码核对后状态 | 本轮补充 |
|---|---|---|---|
| Agent/Workflow 双心智模型 | 已有 | 正确，但缺内部边界 | `SOURCE_DEEP_DIVE` §2–§3 |
| SessionContext/providers | Part 2 较完整 | 需补 History 跳过分支和 provider 顺序 | §3.2、§4 |
| Tool Loop | Part 1/2 已有 | 审批 occurrence 与 indeterminate 更深 | §5 |
| Streaming | 有调用链 | 缺“最终化才是成功边界” | §6 |
| File session | 有概念 | 缺原子写、跨进程 last-writer-wins | §4.2 |
| Workflow | Part 3 有 superstep | 缺 commit/discard、checkpoint lineage 细节 | §7 |
| Harness | 有 provider 清单 | 缺装配时机和后台 task 回收 | §8 |
| Hosting | 有 API 概念 | 缺 hosting 不负责鉴权/路由/single writer | §9–§10 |
| 多租户 | 零散提及 | 应成为后端明确责任 | §10、下表 |
| 源码索引 | 有旧路径 | 需按当前包布局重排 | §11 + 本文 E1–E13 |

## 4. 真正缺口与建议

### 4.1 不是缺失：已由源码覆盖的能力

- Session snapshot 序列化与 FileSessionStore 原子替换；
- Tool approval 的 occurrence、claim、settlement、indeterminate；
- Workflow checkpoint 的 graph signature 和恢复；
- Harness 的 compaction、skills、memory、background agents；
- Streaming 的 close/cleanup/finalizer 语义。

这些不能再写成“框架暂无能力”；正确表述是“框架提供机制，应用仍需接入自己的授权、存储和运营策略”。

### 4.2 文档/集成层的真实缺口

| 缺口 | 风险 | 建议补法 | 优先级 |
|---|---|---|---|
| 同会话并发没有统一生产策略 | last-writer-wins 丢 turn 或重复副作用 | single-writer queue、DB CAS 或分布式锁 | P0 |
| conversation/checkpoint/approval id 未统一 tenant binding | 越权恢复、跨租户读取 | `tenant_id + principal + opaque_id` 授权表 | P0 |
| SSE 断开后的状态未定义 | 工具可能已执行但客户端未收到结果 | indeterminate 状态、幂等键、补偿查询 | P0 |
| caller options/tools allow-list 只在 sample 展示 | 调用者可扩大工具权限 | route 层声明允许字段和工具集合 | P0 |
| 多进程 background task 没有外部协调 | 重启后任务丢失或重复 | durable job queue + task state | P1 |
| checkpoint schema/version 演进策略未写 | 升级后无法恢复旧图 | version migration、graph signature 兼容策略 | P1 |
| provider 顺序未成为扩展契约 | prompt/tools 行为漂移 | 记录顺序、测试组合、禁止隐式重排 | P1 |
| PII/secret 的 snapshot 与 trace 策略不统一 | 泄露到磁盘或日志 | redaction、加密存储、字段 allow-list | P1 |
| 指标与事件命名未统一 | 无法定位模型/工具/审批瓶颈 | trace_id/run_id/session_id 关联规范 | P2 |

### 4.3 需要持续跟踪的上游规范 gap

function-calling loop specification 当前列出一项明确 coverage gap：service-owned `previous_response_id` continuation 在后续 turn 不能再次执行 terminal approval（tracking issue `#6851`）。该项应在升级 Agent Framework 时复核，不应被本地相邻测试替代。

## 5. 生产后端核对表

### 鉴权与租户

- [ ] 每个 session/checkpoint/approval id 都绑定 tenant、principal、权限作用域。
- [ ] resume 请求不能仅凭 opaque id 恢复执行权。
- [ ] provider `service_session_id` 不被当成终端用户授权凭据。

### 一致性与并发

- [ ] 同一 conversation 使用 single-writer 或 CAS。
- [ ] 跨进程 SessionStore/CheckpointStorage 使用共享后端。
- [ ] 并行 tool batch 明确哪些工具可并行、哪些副作用必须串行。
- [ ] run 超时/取消后有回收和幂等策略。

### 流式与恢复

- [ ] stream 消费到最终化才标记成功。
- [ ] 客户端断开能关闭 iterator 和 cleanup hooks。
- [ ] 工具已执行但响应丢失时能查询/补偿，而不是盲目重放。
- [ ] checkpoint 恢复校验 workflow name、graph signature、tenant scope 和 schema version。

### 安全与观测

- [ ] caller options/tools 使用 allow-list。
- [ ] snapshot 明文风险已接受或已加密。
- [ ] 日志包含 trace/run/session 关联但默认不记录敏感 prompt。
- [ ] 审批事件记录 occurrence、owner、generation、最终状态。

## 6. 验证与限制

### 已做的静态验证

- 检查六篇现有文档目录、关键章节及末尾内容并保留原文件内容，采用追加式修改。
- 对照 core、harness、workflow、hosting、responses、AG-UI 关键符号和官方 sample。
- 新增文档的 Mermaid fenced block、内部链接和 Markdown 结构做静态检查。
- 未修改 `agent-framework` 源码。

### 测试尝试（未通过收集阶段）

使用现有 Python 运行 `core/tests/core/test_sessions.py` 与 `core/tests/workflow/test_runner.py`，设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=.../packages/core`，pytest cache 和 basetemp 指向 `/private/tmp/`；`-c /dev/null` 避免项目默认覆盖率输出写入源码目录。

结果：pytest exit code 4，conftest 导入 `_sessions.py` 时缺少 `msgspec`（`ModuleNotFoundError`）；**没有收集/执行目标测试，不能宣称测试通过**。未为此安装依赖。环境中 pytest 为 9.0.0，项目 dev 配置为 9.1.1。建议在依赖匹配环境按照源码规范执行完整 core、AG-UI 与相关包验证。

### 推荐回归入口（本轮未执行成功）

| 入口（相对源码根目录） | 防止什么退化 |
|---|---|
| `python/packages/core/tests/core/test_sessions.py` | snapshot 复制、历史/状态编解码 |
| `python/packages/core/tests/core/test_harness_agent.py` | factory/providers/compaction 装配 |
| `python/packages/core/tests/core/test_harness_background_agents.py` | 后台 task 与 release 生命周期 |
| `python/packages/core/tests/workflow/test_runner.py` | superstep/错误/事件/恢复 |
| `python/packages/core/tests/workflow/test_checkpoint.py` | checkpoint 存储与恢复 |
| `python/packages/hosting/tests/hosting/test_state.py` | factory cache、并发 create-once、独立 working copy |
| `python/packages/ag-ui/tests/ag_ui/test_approval_lifecycle.py` | approval claim/expiry/indeterminate/配额 |

### 未做/限制

- 未安装新依赖，未启动 Azure/Foundry/模型服务。
- 未执行需要云凭据的 hosting sample。
- Mermaid 未在浏览器中渲染；图语法已做围栏和基本结构检查，但最终视觉布局仍需文档站构建验证。
- 本轮没有把每个 provider 包都穷尽到实现级；索引中的 E1–E13 是主链证据，不宣称全仓库形式化覆盖。

### 既有链接债务

旧文档引用的 `./decisions/` 在本目标目录不存在，部分样本链接仍沿用旧目录。为遵守“不删除原文”，未伪造 ADR，也没有把相邻 ADR 当作同一决策；新增导航只链接本次实际存在的文件。未来应单独迁移 ADR 副本或建立可维护的来源映射。

## 7. 本轮文件改动

| 文件 | 改动 |
|---|---|
| `README.md` | 增加源码深读、覆盖矩阵与阅读路径 |
| `ARCHITECTURE.md` | 增加新卷导航 |
| `ARCHITECTURE_PART1.md` | 增加 Agent/Session/Tool/Stream 校准入口 |
| `ARCHITECTURE_PART2.md` | 增加状态、审批、持久化补充入口 |
| `ARCHITECTURE_PART3.md` | 增加 Workflow/Hosting 后端补充入口 |
| `DESIGN_THINKING_SERIES.md` | 增加第十幕：可信边界与失败语义 |
| `SOURCE_DEEP_DIVE_2026.md` | 新增源码级深读主文档，含架构、类图、时序图、状态图和流程图 |
| `COVERAGE_AND_CHANGES.md` | 新增证据索引、覆盖矩阵、缺口和验证说明 |

原文未删除；新增内容位于卷首阅读提示、原文末尾或新文件中。

交付范围：8 个 Markdown 文件（新增 2 个、增补 6 个），新增 20 张 Mermaid 图。已逐行验证原文按原顺序完整保留；源码仓库既有文档删除状态未改动。
