# Codex 文档覆盖、源码证据与改动记录

> 日期：2026-10-15。对应源码 commit：`b7ba02f88095cd3c039709157618c03909d47a26`。
> 本轮是文档补充，不是业务代码改造，也不是全部 crate 的安全审计。

## 目录

- [1. 阅读路径](#1-阅读路径)
- [2. 文档遗漏与源码缺口分开登记](#2-文档遗漏与源码缺口分开登记)
- [3. 当前源码证据索引](#3-当前源码证据索引)
- [4. 回归测试入口](#4-回归测试入口)
- [5. 实际验证结果与边界](#5-实际验证结果与边界)
- [6. 文件改动总结](#6-文件改动总结)

## 1. 阅读路径

| 读者 | 推荐路径 |
|---|---|
| 架构设计 | [新源码深读 §2](./SOURCE_DEEP_DIVE_2026.md#2-全局事实地图) → §4 → §9 → §12 |
| 后端并发开发 | [入口 §3](./SOURCE_DEEP_DIVE_2026.md#3-入口与控制面) → §5 → §11 |
| 工具/扩展开发 | [工具 §7](./SOURCE_DEEP_DIVE_2026.md#7-工具审批沙箱与-guardian) → §10 → 原 PART2 |
| 上下文/模型开发 | [执行 §6](./SOURCE_DEEP_DIVE_2026.md#6-run_turn-的阶段化执行) → §8 → 原 CONTEXT_MANAGEMENT |
| 故障排查 | 原 ENTITY_AND_SEQUENCES → 新 §5/§9/§11 → 本页回归入口 |

## 2. 文档遗漏与源码缺口分开登记

### 2.1 本轮已补足的文档内容

- 将连接初始化、experimental capability、TurnAdmission、资源串行化与 core input admission 放在同一条链路中。
- 明确 RPC 排队与 handler 启动不同，持有准入 permit 与 turn 已运行不同。
- 补充 GlobalSharedRead 合并批次、写请求的队首屏障及关闭连接等待项清理。
- 校准 SQ=512、transport=128、rollout writer=256 与 unbounded EQ 的不同背压边界。
- 补充 ModelClient/ModelClientSession 的 lifetime，以及 session-scoped HTTP fallback。
- 补充 Router/Registry/Parallel/Orchestrator 的职责；说明工具审计 recorder 不执行工具。
- 区分已有 MCP attribution 与建议 endpoint/schema fingerprint；避免将已有审计误写为缺失。
- 补充后台压缩候选的 generation/model/auth 条件及 session-owned 任务生命周期。
- 解释 LocalThreadStore 的 flush-before-SQLite projection 与 EventMsg 错误后仍可 deliver 的区别。
- 补充 daemon interruption snapshot 的 local environment/recorded input 准入和快照消费。
- 展开 slow-client disconnect、ordinary drain、force signal、connection gate 与 cleanup 的不同语义。

### 2.2 源码直接可见的改进点

`core/src/session/turn.rs::run_turn` 在 pre-turn compaction 前有 TODO：估算即将写入的 context diffs/full reinjection + user input，并在其会超过阈值时预先触发 compaction。

这条 TODO 能支持“待输入预算估算需要深化”，不能扩展成“没有 token budget”或“没有 compaction”。后续测试应构造现有 history 接近阈值、单条新 user prompt/context diff 大幅增大的场景，并验证输入保存与错误后恢复。

### 2.3 尚待专项审计的候选问题

| 候选问题 | 已有能力 | 还需要什么证据 |
|---|---|---|
| 外部工具 exactly-once | call identity、best-effort ExecutedToolCalls、seen-id | 外部服务幂等键、commit receipt、崩溃重放测试 |
| 所有 UI 事件的断电恢复 | persistence policy、writer flush、局部 flush barriers | fsync/存储语义、append 失败注入、断电模型 |
| 所有入口统一权限主体 | connection auth/current owner、effective profiles | 跨 remote/in-process/daemon 恢复的身份矩阵 |
| 资源队列长期压力 | bounded transports、queued Gauge、slow-client disconnect | per-key enqueue 上限、压力测试、延迟/峰值指标 |
| 扩展配置变更兼容 | refresh、tool exposure、MCP attribution | schema/endpoint/config fingerprint 与运行中调用兼容性 |
| 子进程停止保证 | cancellation、工具 runtime、tree shutdown | 平台差异、reap/timeout/强制终止故障注入 |

以上不是已复现漏洞，也不是完整能力缺失结论；不能依据一次字符串检索为全仓库能力下否定判断。

## 3. 当前源码证据索引

下列路径以 `/Users/gqli/work/deepagents/codex/codex-rs/` 为根。以符号而非历史行号作为定位依据。

| 主题 | 文件 | 本轮核对点 |
|---|---|---|
| 请求初始化与双重准入 | `app-server/src/message_processor.rs` | `dispatch_initialized_client_request`、`serialization_scope()`、admit/recheck |
| turn 启动/服务 drain | `app-server/src/turn_admission.rs` | `TurnAdmission`、`TurnPermit`、`try_admit`、Drop |
| 资源队列 | `app-server/src/request_serialization.rs` | `RequestSerializationQueues`、`from_scope`、`drain`、`discard_closed` |
| 连接权限与关闭 | `app-server/src/connection_rpc_gate.rs` | `run`、`is_closed`、`close`、`shutdown` |
| 服务器双循环/关闭 | `app-server/src/lib.rs` | `OutboundControlEvent`、`ShutdownState`、main loop counters |
| 慢连接 | `app-server/src/transport.rs` | `send_message_to_connection`、`try_send` Full/Closed |
| 传输类型/容量 | `app-server-transport/src/transport/mod.rs` | `AppServerTransport`、`CHANNEL_CAPACITY` |
| Thread 门面 | `core/src/codex_thread.rs` | SessionIo、residency gate、submit/next_event、shutdown |
| Thread 生命周期 | `core/src/thread_manager.rs` | `start_thread`、`resume_thread_with_history`、`shutdown_all_threads_bounded` |
| Session state/services | `core/src/session/session.rs` | 独立 state、active turn、settings persistence、input_queue |
| 通道/事件/持久化 | `core/src/session/mod.rs` | `SessionIo`、SQ/EQ、`send_event_raw_with_persistence`、`persist_rollout_items` |
| submission loop | `core/src/session/handlers.rs` | shutdown/select/mailbox/Op 分发 |
| 输入分层 | `core/src/session/input_queue.rs` | `InputQueue`、`TurnInputQueue`、mailbox activity |
| turn 完成 | `core/src/session/turn.rs` | `run_turn`、`needs_follow_up`、hooks、预压缩 TODO |
| 当前任务状态 | `core/src/state/turn.rs` | `ActiveTurn`、`RunningTask`、pending waiter、mailbox phase |
| provider lifetime | `core/src/client.rs` | `ModelClient`、`ModelClientSession`、sticky state、fallback |
| 工具路由/注册 | `core/src/tools/router.rs`、`registry.rs` | model-visible specs、ToolRegistry、CoreToolRuntime |
| 工具并发 | `core/src/tools/parallel.rs` | `ToolCallRuntime`、parallel_execution、cancellation |
| 审批与 sandbox | `core/src/tools/orchestrator.rs` | attempt、network approval、远程 capability 安全检查 |
| 调用记录 | `core/src/tools/executed_tool_calls.rs` | bounded best-effort、completeness、DirectCallPermit |
| MCP 来源 | `core/src/tools/executed_tool_calls/mcp_attribution.rs` | source identity、revision、checkpoint |
| 后台压缩 | `core/src/session/async_compaction.rs` | enable gates、take_ready、wait_for_pending、shutdown |
| Live persistence | `thread-store/src/live_thread.rs` | `append_items`、policy、metadata sync |
| Canonical write/view | `thread-store/src/local/live_writer.rs` | `write_and_project`、`durable_write`、flush-before-projection |
| Rollout writer | `rollout/src/recorder.rs` | queue=256、Flush ack、重开/重试、file flush |
| daemon snapshot | `app-server-transport/src/daemon_recovery.rs` | loaded/interrupted、metadata prefix、local identity |
| interruption 准入 | `core/src/session/daemon_recovery.rs` | RecordedTurnInput、Regular/local/FromThread、caller flush |
| 快照消费 | `app-server/src/daemon_thread_recovery.rs` | snapshot thread、read/remove、后台 restore |

[边界] 上表重点核对实际代码分支。Plugins、Skills、Realtime、memories、多 Agent 和平台 sandbox 的全部实现没有逐行重审；这些部分保持原专题文档为主，新章提供跨层导航，而不是宣称全仓库重新审计完成。

## 4. 回归测试入口

| 场景 | 当前已有测试入口 | 检查目标 |
|---|---|---|
| admission 关闭竞态 | `app-server/src/turn_admission_tests.rs` | 已准入 permit 仍计数，新启动被拒绝 |
| key FIFO/跨 key 并发 | `app-server/src/request_serialization.rs` tests | same_key_requests_run_fifo、different_keys_run_concurrently |
| 共享读/写公平 | 同上 | later_shared_read_waits_behind_writer_queued_during_running_read |
| 关闭 gate | `app-server/src/connection_rpc_gate.rs` tests | late future 不 poll，started work 被等待 |
| transport | `app-server/src/transport_tests.rs` | connection routing/filtering/slow client behavior，按用例精查 |
| 后台压缩 | `core/src/session/async_compaction_tests.rs` | cancelled turn 不启动新任务，保留既有任务 |
| 工具调用记录 | `core/src/tools/executed_tool_calls_direct_tests.rs` | Direct 调用记录与截断/完成信息 |
| 并行工具 | `core/src/tools/parallel_observation_tests.rs` | 工具并发观察/记录，不只响应顺序 |
| SQLite 物化 | `thread-store/src/local/thread_history_materialization_tests.rs` | canonical rollout 与 projection 的一致性 |
| daemon 管理 | `app-server-daemon/src/thread_recovery.rs` | 与 recovery snapshot 链路联读，补充故障注入 |

测试矩阵是回归入口定位，不是通过报告。针对候选问题需要编写独立 failure injection，而不应把已有 happy-path 用例当作所有恢复安全性的证据。

## 5. 实际验证结果与边界

### 5.1 静态检查

- 保留原有 Markdown 内容及顺序，仅增加导航/追加说明。
- 对新增完整源码路径做存在性检查，对关键 struct/fn/constant 做源码字面核对。
- 检查新增目录 anchors、文件链接、代码围栏与新增 Mermaid block 结构。
- 不替换已有 `diagrams/` 的 HTML、JSON 或截图；本次新增图解采用正文内 Mermaid。
- 未逐张做 Mermaid 浏览器渲染验证，结构检查不能冒充视觉验证。

### 5.2 动态验证尝试

项目 `rust-toolchain.toml` 指定 Rust 1.95.0；本机仅发现 Rust 1.96.1。为避免自动安装 toolchain，尝试用现有工具链离线测试：

```bash
cargo +1.96.1 test --offline --locked \
  --manifest-path /Users/gqli/work/deepagents/codex/codex-rs/Cargo.toml \
  --target-dir /private/tmp/codex-doc-validation-target \
  -p codex-app-server --lib turn_admission --no-fail-fast
```

结果：Cargo 在解析 pinned git 依赖 `openai-oss-forks/tungstenite-rs` 时停止，原因是 offline 模式下不能 checkout 缺失依赖。**没有完成编译，没有执行测试用例，不是测试断言失败。** 没有下载依赖、修改 lockfile、启动模型/API/GUI 或执行外部工具副作用。

建议在已配置的开发环境、按项目指定工具链分别运行：

```bash
cd /Users/gqli/work/deepagents/codex/codex-rs
cargo test --locked -p codex-app-server --lib turn_admission
cargo test --locked -p codex-app-server --lib request_serialization
cargo test --locked -p codex-app-server --lib connection_rpc_gate
```

这些是建议回归命令，不是本次通过的结果。成功后再追加版本、通过/跳过数和失败原因。

## 6. 文件改动总结

| 文件 | 改动方式 | 说明 |
|---|---|---|
| `SOURCE_DEEP_DIVE_2026.md` | 新增 | 13 节源码深读、架构/类/时序/流程/状态图、注释代码与风险分类 |
| `COVERAGE_AND_CHANGES.md` | 新增 | 证据、测试、覆盖边界与本次交付总结 |
| `README.md` | 仅添加 | 新阅读路径和快照基线说明 |
| `ARCHITECTURE.md` | 仅添加 | 新专题导航与简短校准说明 |
| `ARCHITECTURE_PART1.md` | 文末追加 | 核心循环/模型传输/后台压缩的校准指引 |
| `ARCHITECTURE_PART2.md` | 文末追加 | 工具主链、审批升级、已有审计与新章的连接 |
| `ARCHITECTURE_PART3.md` | 文末追加 | flush-before-projection、daemon 恢复与失败传播边界 |

**最终结论**：原文的 Agent Loop、安全与三种真相已有较高深度；本轮的增量价值是把控制面、并发粒度、状态所有权、持久化屏障、关闭和恢复准入联成可验证链路，而不是简单增加更多模块名。
