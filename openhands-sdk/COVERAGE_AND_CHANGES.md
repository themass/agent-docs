# OpenHands SDK 文档覆盖、源码证据与缺口

## 目录

- [1. 范围与基线](#1-范围与基线)
- [2. 证据索引](#2-证据索引)
- [3. 覆盖矩阵](#3-覆盖矩阵)
- [4. 真正缺口](#4-真正缺口)
- [5. 验证限制](#5-验证限制)
- [6. 本轮改动](#6-本轮改动)

## 1. 范围与基线

本轮核对 `software-agent-sdk/openhands-sdk`、`openhands-agent-server` 及其与 Agent Canvas 的边界；不修改兄弟源码。原有文档已覆盖 Agent、Conversation、Event、View、Condenser、Tool、MCP、Security、Persistence 和 Testing，但对宿主并发、断线恢复、外部副作用和 SDK/Server 责任边界仍可加深。

## 2. 证据索引

| ID | 源码 | 结论 |
|---|---|---|
| S1 | `LocalConversation.send_message/run/_run/arun` | 外层 loop、状态转换、预算和异常 |
| S2 | `ConversationState` + `FIFOLock` | 进程内状态所有权与顺序 |
| S3 | `EventLog` | 事件追加、索引、路径恢复 |
| S4 | `View` / `Condenser` | 事件到 prompt 的投影和压缩 |
| S5 | `EventService.run` | run slot、后台执行、native async/线程 fallback |
| S6 | `ConversationLease` | 持久化会话的 owner/generation/续租 |
| S7 | `LocalWorkspace`/remote workspace | 工具副作用和隔离 |
| S8 | `Agent Server routers/pub_sub` | REST/WebSocket/事件推送边界 |

## 3. 覆盖矩阵

| 主题 | 原文 | 本轮校准 |
|---|---|---|
| Conversation loop | 已有 | 补状态锁、并发消息不丢失、终止条件 |
| Event sourcing | 已有 | 补 event cursor、View 游标与重连 |
| Condenser | 已有 | 补“压缩 prompt 不删除原始事件” |
| Tool/MCP | 已有 | 补确认恢复与副作用幂等 |
| Agent Server | 有独立文档 | 补 Lease、RunSlot、EventService 宿主边界 |
| Workspace | 零散 | 补工作区与 EventLog 非原子关系 |
| ACP/子 Agent | 零散 | 补进程、会话、资源释放 |
| 多租户/恢复 | 不足 | 补生产后端清单 |

## 4. 真正缺口

### 已有而不应误报为缺失

- 本地状态锁和 FIFO 等待；
- EventLog 持久化和路径恢复；
- ConversationLease 及 lease renewal；
- Agent Server 的 run slot、事件订阅和 WebSocket 推送；
- Condenser、Tool confirmation、ACP/远程 Conversation 结构。

### 后端契约与测试仍应补深

下列项目是审计/演练清单，不是未经验证的“源码不存在”结论。

1. 已实现 WebSocket cursor/replay；补充乱序、坏事件、背压与分页一致性验收。
2. lease owner 与工具副作用的幂等/补偿关系。
3. EventLog、base state、meta 和 credentials 的恢复扫描。
4. conversation、workspace、MCP server、ACP 进程的租户隔离。
5. schema migration、事件兼容、旧客户端降级。
6. 对断连、取消、超时、进程重启和 provider 错误分别定义状态。
7. 观测字段脱敏，避免 prompt、token、secret 进入事件和日志。

### 静态定位到的异常清理缺口

`subscribe_to_events` 注册后若初始 snapshot/推送抛出非 TimeoutError，id 未返回且未回滚；session socket 异常分支只能清理 writer/socket，不能 reclaim registration。详见深读 §13。源码可定位，但未做运行时故障注入。

## 5. 验证限制

已完成源码静态阅读、符号/路径核对、文档新增 Mermaid 围栏和链接检查。未安装新依赖，未连接真实 LLM、MCP、ACP、Docker 或 Agent Server；没有把静态分析描述成端到端通过。SDK 原仓库本身存在既有文档删除状态，本轮未恢复或修改。定向 pytest 尝试因该仓库 `.venv` 缺少 `pytest` 而无法执行；未安装依赖。关联 Canvas 游标测试 6 项通过。

## 6. 本轮改动

- 新增 `SOURCE_DEEP_DIVE_2026.md`：源码级架构、类图、时序图、状态图、后端责任。
- 新增本文件：覆盖矩阵、真实缺口、证据索引和限制。
- 原有 README、ARCHITECTURE 和三卷文档仅追加导航/校准，不删除原文。

### 最终静态验证记录

- 8 份 SDK 原始文档逐字节保留为现文件前缀，没有改写或移除原内容。
- 新增相对文件链接均能解析到本地文件；Markdown 代码围栏配对通过；`git diff --check` 通过。
- 通过 Python AST 核对 LocalConversation、EventLog、View、CondenserBase、LLMConvertibleEvent 共 5 个关键类及类图方法。
- Mermaid 未执行实际渲染验收。两份源码仓库的既有 Git 状态未新增业务改动。
