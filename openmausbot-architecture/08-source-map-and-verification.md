# 08 源码导航、验证与设计取舍

## 目录

- [1. 主干源码阅读顺序](#reading)
- [2. 外围模块地图与本轮深度](#perimeter)
- [3. 最重要的设计不变量](#invariants)
- [4. 验证方法与本轮未验证范围](#verification)
- [5. 从实现得到的设计取舍](#tradeoffs)
- [6. 本轮文档交付说明](#changes)
- [7. 固定基线的源码跳转](#evidence)

<a id="reading"></a>
## 1. 主干源码阅读顺序

不要从 `index.ts` 第一行一直读到最后。按一个问题的输入、状态、输出往返读：

1. **边界契约**：`contracts.ts` → `shared/wire.ts` → `shared/runtime-events.ts`。
2. **用户发送**：`acceptDirectSend` → `admit` → `startOrQueueDirectMessage` → `startTurn`。
3. **模型所见**：`Store.activePath` → `directContext` → `selectReplay` → `buildTurnContext` → `buildSystemPrompt` → adapter。
4. **结果回写**：adapter.onEvent → EventBus → index.ts 事件归约 → Store append/patch → DB → SSE。
5. **多 Agent**：CoordinatorHost → RuntimeCoordinator → Runtime → RuntimeStore → runner.run/report/park。
6. **审批**：request.opened → autoVerdict/卡片 → answerRequest → 原 adapter.respondToRequest。
7. **恢复**：Store thread cache、followup restore、Runtime.open、native cursor/recoveryText 分别读，不能混成一个 restore 函数。

<a id="perimeter"></a>
## 2. 外围模块地图与本轮深度

为防止“只介绍核心循环，就误以为所有模块讲完”，这里列明外围系统及深度。**入口确认**表示定位了目录/接口，不表示整个子系统已做源码逐分支分析。

| 领域 | 源码入口 | 本轮深度 / 阅读边界 |
|---|---|---|
| 桌面宿主与子进程 | `electron/main.mjs`、`server-supervisor.mjs`、`server-child-launch.mjs`、`preload.cjs` | 入口确认；桌面权限与 IPC 全协议未展开 |
| 前端页面、状态与实时连接 | `src/components/`、`src/state/store.tsx`、`src/lib/live-events.ts` | 深读快照/SSE主链；未逐个组件说明 |
| Host 渐进拆分 | `server/host/README.md`、`room-sessions.ts`、`room-transcript.ts` 等 | 已读模块规则；index.ts 仍是 composition root |
| HTTP 路由 | `server/routes/README.md`、`table.ts` 及领域 routes | 已读装配规则；不是 endpoint 逐项 API 手册 |
| 设备伴随服务 | `companion/src/`：devices/listener/mdns/proxy/routes 等 | 入口确认；发现、配对和传输协议未深展开 |
| 云控制与连接代理 | `cloudflare/control-plane`、`cloudflare/composio-broker` | 目录边界确认；不推断与本机 DB 强一致 |
| 多 workspace 运维 | `server/fleet.ts`、`deploy/`、`enterprise/` | fleet 是 OS 用户/systemd 工作区规划，不是 ProviderRegistry |
| 内部工具与 MCP | `server/drivers/agents-*`、MCP bridge/gate/proxy 等 | 深读挂载契约、结果预算与权限关联；未遍历所有第三方工具 |
| 电脑/浏览器/手机/数据 | computer、browser、phone、data 相关模块 | 已读资源所有权和挂载；具体远端后端协议未全部验证 |
| 外部聊天接入 | `routes/hosted-slack.ts`、`routes/channels.ts` 等 | 核对路由入口与访问风险；不能把 UI 房间等同全部外部 channel |
| 语音、电话与 TTS | `server/tts/`、index.ts 中 liveCalls/calendarCalls 相关装配 | 入口确认；音视频会话时序未展开 |
| 运维观察 | `server/sentinel/scan.ts`、detectors、store | 核对扫描工具/turn/queue 记录及问题持久化；不是权限裁决器 |
| 用量、决策与管理日志 | usage ledger、decision log、admin activity 相关模块 | 核对退出 flush；未将其误说成与消息 DB 的统一事务 |
| 工具 hooks | `server/hooks/omb-hook.ts`、SendTurnInput.integrations.hooks | 契约核对：观察/注入，不决定业务状态 |
| 评测与验证 | `evals/`、`docs/verification/`、`server/testing/` | 阅读验证规范与代表测试入口；未运行全量评测 |

### 正在进行的模块化方向

`server/host/README.md` 说明从 index.ts 按 concern 迁移，采用 `createArea(deps)` 显式依赖，状态随代码迁移，保留顶层 await 和订阅顺序；host 模块不反向 import index.ts。

`server/routes/README.md` 要求 `createXRoutes(deps)` 返回 handler，不属于自己的请求返回 `PASS`；路由表运行在 auth gate 后。这个结构是正在落地的拆分，不应把迁移目标画成已经完成的实际部署架构。

<a id="invariants"></a>
## 3. 最重要的设计不变量

| 不变量 | 守住它的机制 | 违反后的典型问题 |
|---|---|---|
| 同一发送不应静默跑两遍 | sendId 幂等、command receipts、steer indeterminate 不重排 | 外部副作用重复 |
| 未执行的 followup 不抢走当前分支 | off-transcript durable queue | 模型历史包含尚未收到的指令 |
| 旧分支/过期摘要不能遮住新历史 | compaction 双锚点、activePath、prefix/generation 检查 | 历史丢失或错误总结覆盖纠正 |
| 新轮不能继承旧轮内部授权 | turn generation capability 撤销/绑定 | 迟到的工具操作越权 |
| 审批必须回答原 live request | threadId:requestId、runningTurnEngines、真实 outcome | 批错工具或批准不存在的现场 |
| 设备截图和操作应看到同一现场 | TurnResources 整轮 owner | 错位点击、互相干扰 |
| 已有外部副作用的中断任务不能盲重跑 | Runtime.open 的 outward evidence 分支 | 重复发送/重复发布 |
| 新事件不能被旧快照覆盖 | hello 后 hydration、pending frames、序列与 gap | UI 退回旧状态 |

<a id="verification"></a>
## 4. 验证方法与本轮未验证范围

### 本轮实际验证

- 只读本地源码，固定 package version / git commit。
- 校验文档内部链接、目录锚点、Markdown 围栏；源码索引校验文件、行号、匹配文本与 SHA-256。
- 不修改源项目，不启动真实 bot，不触碰 live 数据，不发送第三方请求。
- 不把“读到一个测试文件”写成“该测试已通过”。

复查文档：

```sh
python3 /Users/gqli/work/deepagents/docs/openmausbot-architecture/verify_docs.py
```

检查脚本另有 `test_verify_docs.py` 的 6 个回归测试，覆盖正常文档、断链、缺失锚点、未闭合围栏、源码行号漂移及摘要漂移；本轮实际执行通过。可运行 `python3 -B test_verify_docs.py` 复查（在本文档目录）。

该脚本是**静态一致性检查**：不会验证 Mermaid 在指定渲染器中的最终排版，也不能证明源码运行逻辑正确。源码变更后 hash/commit 检查会失败，要求重新核对，而不是默默继续使用旧行号。

### 将来验证运行行为应怎么做

源项目 `docs/verification/README.md` 要求使用 isolated fixture；推荐从该仓库启动 `scripts/control-omb.ts launch`，它创建临时 data/home 和 fake engine，再显式传入打印出的 URL 进行控制。不能通过默认端口探测误连用户真实应用。

优先场景：

1. 不压缩：发送 → 流式输出 → terminal → 重启后消息一致。
2. 压缩：摘要追加、旧消息保留、新 session/replay 生效；Stop 期间晚摘要不提交。
3. steer：steered/refused/indeterminate 三态；确认没有双执行。
4. followup：排队 → Stop → 重启 → 正确保留 pending；不重放已交付 held 项。
5. 多 Agent：父 waiting、子结束/report、父 resume；outward 中断不盲重跑。
6. 审批：同 thread/request 精确回答；换模型后仍答旧实例；请求过期 fail closed。
7. 权限：个人/共享默认、guest、toolScope、safetyFloor enabled/disabled 的不同结果。

这些是后续建议场景，**本轮没有运行，因此不报告通过数或端到端行为结论**。

<a id="tradeoffs"></a>
## 5. 从实现得到的设计取舍

- **适配复杂性换产品统一**：用户以相同聊天操作使用不同引擎，但能力、审批、恢复仍需具体 driver 实现，不能靠一个接口自动获得一致性。
- **保留聊天事实、按需构造模型上下文**：回退、切换引擎和摘要后可重新投影；代价是必须维护分支、handed state、context anchors，不能只数数组长度。
- **durable work 而非 durable stack**：任务可以恢复与交付，代价是每种中断都要判断是否能安全重放。
- **分离多个存储通道**：SQLite 消息、runtime.db、文件记忆、事件日志各有优化目标；代价是不存在一个“全应用 flush 原子成功”的简单承诺。
- **可用性优先但不伪造确定性**：不可用引擎保留 shadow、steer 不确定不重送、审批 unavailable 不冒充成功，减少静默错误。
- **安全必须看实际执行路径**：full 默认、service loopback 风险、floor 适用范围都有明确边界；不能根据漂亮的架构图得出强隔离结论。

<a id="changes"></a>
## 6. 本轮文档交付说明

新增独立文档集，不改动 Hermes、其他项目文档或 OpenMausBot 源码。按架构、状态、执行、协作、工具、安全、长期能力分章；各章带可见目录与真实实体图。

附带证据清单和只读静态检查脚本。核心主链源码已深读，外围覆盖深度如上表明确标注；这是一份可继续增补的基线，而不是“所有文件都已经审计完毕”的承诺。

<a id="evidence"></a>
## 7. 固定基线的源码跳转

下表由 `source-evidence.json` 生成；行号只适用于本文固定提交。源码中的实现定义与调用点分开列出，避免把字段名字误当函数。

| 源码文件 | 定义 / 关键调用点 |
|---|---|
| `server/contracts.ts` | [export interface SendTurnInput](../../personal-agent/OpenMausBot/server/contracts.ts#L83)；[export interface ProviderAdapter](../../personal-agent/OpenMausBot/server/contracts.ts#L179)；[export interface ProviderInstance](../../personal-agent/OpenMausBot/server/contracts.ts#L386)；[export interface ProviderDriver](../../personal-agent/OpenMausBot/server/contracts.ts#L422) |
| `shared/wire.ts` | [export interface WireMessage](../../personal-agent/OpenMausBot/shared/wire.ts#L396) |
| `shared/approval-mode.ts` | [export const APPROVAL_MODES](../../personal-agent/OpenMausBot/shared/approval-mode.ts#L5)；[export const DEFAULT_APPROVAL_MODE](../../personal-agent/OpenMausBot/shared/approval-mode.ts#L51)；[export function approvalModeFor](../../personal-agent/OpenMausBot/shared/approval-mode.ts#L63) |
| `shared/runtime-events.ts` | [export type RuntimeEvent](../../personal-agent/OpenMausBot/shared/runtime-events.ts#L38) |
| `server/index.ts` | [const registry = new ProviderRegistry](../../personal-agent/OpenMausBot/server/index.ts#L794)；[await registry.load](../../personal-agent/OpenMausBot/server/index.ts#L1593)；[bus.attach(registry.instances())](../../personal-agent/OpenMausBot/server/index.ts#L1698)；[const store = new Store](../../personal-agent/OpenMausBot/server/index.ts#L3341)；[async function acceptDirectSend](../../personal-agent/OpenMausBot/server/index.ts#L8052)；[async function startOrQueueDirectMessage](../../personal-agent/OpenMausBot/server/index.ts#L8001)；[async function startTurn](../../personal-agent/OpenMausBot/server/index.ts#L8451)；[async function compactConversation](../../personal-agent/OpenMausBot/server/index.ts#L7868)；[const contextReset =](../../personal-agent/OpenMausBot/server/index.ts#L8740)；[if (contextReset && record)](../../personal-agent/OpenMausBot/server/index.ts#L9378)；[async function answerRequest](../../personal-agent/OpenMausBot/server/index.ts#L5536)；[case "request.opened"](../../personal-agent/OpenMausBot/server/index.ts#L7240)；[function broadcast(](../../personal-agent/OpenMausBot/server/index.ts#L5481)；[restoreSteeredMessages();](../../personal-agent/OpenMausBot/server/index.ts#L17621)；[server.listen(PORT](../../personal-agent/OpenMausBot/server/index.ts#L17632)；[const gracefulShutdown =](../../personal-agent/OpenMausBot/server/index.ts#L17683) |
| `server/store.ts` | [export class Store](../../personal-agent/OpenMausBot/server/store.ts#L437)；[private cacheThread(](../../personal-agent/OpenMausBot/server/store.ts#L1266)；[activePath(threadId:](../../personal-agent/OpenMausBot/server/store.ts#L1317)；[appendMessage(threadId:](../../personal-agent/OpenMausBot/server/store.ts#L1341) |
| `server/message-db.ts` | [CREATE TABLE IF NOT EXISTS messages (](../../personal-agent/OpenMausBot/server/message-db.ts#L35)；[CREATE TABLE IF NOT EXISTS chat_followups](../../personal-agent/OpenMausBot/server/message-db.ts#L54)；[CREATE TABLE IF NOT EXISTS thread_state](../../personal-agent/OpenMausBot/server/message-db.ts#L50) |
| `server/context-rebuild.ts` | [export function selectReplay](../../personal-agent/OpenMausBot/server/context-rebuild.ts#L179)；[export function boundedContextText](../../personal-agent/OpenMausBot/server/context-rebuild.ts#L168)；[export const REPLAY_TOOL_LINE_CAP](../../personal-agent/OpenMausBot/server/context-rebuild.ts#L23) |
| `server/compaction-summary.ts` | [export function foldPoint](../../personal-agent/OpenMausBot/server/compaction-summary.ts#L5)；[export async function draftSummary](../../personal-agent/OpenMausBot/server/compaction-summary.ts#L43) |
| `server/turn-context.ts` | [export function buildTurnContext](../../personal-agent/OpenMausBot/server/turn-context.ts#L57)；[export function buildRecoveryText](../../personal-agent/OpenMausBot/server/turn-context.ts#L41) |
| `server/context-budget.ts` | [export function](../../personal-agent/OpenMausBot/server/context-budget.ts#L7) |
| `server/system-prompt.ts` | [export function buildSystemPrompt](../../personal-agent/OpenMausBot/server/system-prompt.ts#L41)；[VOLATILE_SECTIONS](../../personal-agent/OpenMausBot/server/system-prompt.ts#L18) |
| `server/steer-queue.ts` | [export function restoreSteeredMessages](../../personal-agent/OpenMausBot/server/steer-queue.ts#L51)；[export function queueSteeredMessage](../../personal-agent/OpenMausBot/server/steer-queue.ts#L97) |
| `server/admission.ts` | [export function admit(](../../personal-agent/OpenMausBot/server/admission.ts#L84) |
| `server/harness/registry.ts` | [export class ProviderRegistry](../../personal-agent/OpenMausBot/server/harness/registry.ts#L50) |
| `server/harness/bus.ts` | [export class EventBus](../../personal-agent/OpenMausBot/server/harness/bus.ts#L44) |
| `server/drivers/builtIn.ts` | [BUILT_IN_DRIVERS](../../personal-agent/OpenMausBot/server/drivers/builtIn.ts#L25) |
| `server/drivers/openai-chat.ts` | [export function createOpenAIChatRuntime](../../personal-agent/OpenMausBot/server/drivers/openai-chat.ts#L265)；[const messagesFor =](../../personal-agent/OpenMausBot/server/drivers/openai-chat.ts#L477) |
| `server/coordinator.ts` | [export interface CoordinatorHost](../../personal-agent/OpenMausBot/server/coordinator.ts#L97)；[export interface Coordinator {](../../personal-agent/OpenMausBot/server/coordinator.ts#L116)；[export function createCoordinator](../../personal-agent/OpenMausBot/server/coordinator.ts#L166) |
| `server/runtime-coordinator.ts` | [export class RuntimeCoordinator](../../personal-agent/OpenMausBot/server/runtime-coordinator.ts#L97)；[requests: REQUESTS_PER_ROOT](../../personal-agent/OpenMausBot/server/runtime-coordinator.ts#L119)；[private ready():](../../personal-agent/OpenMausBot/server/runtime-coordinator.ts#L125) |
| `server/runtime/runtime.ts` | [export class Runtime](../../personal-agent/OpenMausBot/server/runtime/runtime.ts#L47)；[open():](../../personal-agent/OpenMausBot/server/runtime/runtime.ts#L76)；[private finishTurn(](../../personal-agent/OpenMausBot/server/runtime/runtime.ts#L414)；[private report(](../../personal-agent/OpenMausBot/server/runtime/runtime.ts#L611)；[private wake(](../../personal-agent/OpenMausBot/server/runtime/runtime.ts#L626) |
| `server/runtime/store.ts` | [CREATE TABLE IF NOT EXISTS assignments](../../personal-agent/OpenMausBot/server/runtime/store.ts#L108)；[CREATE TABLE IF NOT EXISTS inbox](../../personal-agent/OpenMausBot/server/runtime/store.ts#L140)；[export function openRuntimeStore](../../personal-agent/OpenMausBot/server/runtime/store.ts#L191) |
| `server/runtime/types.ts` | [export interface Assignment](../../personal-agent/OpenMausBot/server/runtime/types.ts#L80)；[export interface TurnRunner](../../personal-agent/OpenMausBot/server/runtime/types.ts#L270) |
| `server/channel-queue.ts` | [export function holdChannelQueue](../../personal-agent/OpenMausBot/server/channel-queue.ts#L115)；[export function settleHeldChannelQueueHead](../../personal-agent/OpenMausBot/server/channel-queue.ts#L148) |
| `server/turn-resources.ts` | [export class TurnResources](../../personal-agent/OpenMausBot/server/turn-resources.ts#L10) |
| `server/permission-proxy.ts` | [function askBroker(](../../personal-agent/OpenMausBot/server/permission-proxy.ts#L56) |
| `server/request-auth.ts` | [export const SERVICE_ALLOW](../../personal-agent/OpenMausBot/server/request-auth.ts#L33) |
| `server/safety-floor-gate.ts` | [export function safetyFloorEnabled](../../personal-agent/OpenMausBot/server/safety-floor-gate.ts#L15)；[export function heldAtSafetyFloor](../../personal-agent/OpenMausBot/server/safety-floor-gate.ts#L98)；[export function denyAtSafetyFloor](../../personal-agent/OpenMausBot/server/safety-floor-gate.ts#L104) |
| `server/mcp-trim.ts` | [export const DEFAULT_RESULT_BUDGET](../../personal-agent/OpenMausBot/server/mcp-trim.ts#L1) |
| `server/mcp-result-budget.ts` | [export function attachCustomMcp](../../personal-agent/OpenMausBot/server/mcp-result-budget.ts#L17) |
| `server/memory-store.ts` | [export function parseMemoryPath](../../personal-agent/OpenMausBot/server/memory-store.ts#L53) |
| `server/memory-capture.ts` | [export function capturePrompt](../../personal-agent/OpenMausBot/server/memory-capture.ts#L53)；[export class CaptureBuffer](../../personal-agent/OpenMausBot/server/memory-capture.ts#L172) |
| `server/memory-upkeep.ts` | [export const CAPTURE_MAX_TURNS](../../personal-agent/OpenMausBot/server/memory-upkeep.ts#L14) |
| `server/skills.ts` | [export function skillsSystemPrompt](../../personal-agent/OpenMausBot/server/skills.ts#L1261)；[export function stageSkillWrite](../../personal-agent/OpenMausBot/server/skills.ts#L986)；[export function applyStagedSkillWrite](../../personal-agent/OpenMausBot/server/skills.ts#L1142) |
| `server/routines.ts` | [export class RoutineManager](../../personal-agent/OpenMausBot/server/routines.ts#L676) |
| `server/decider/room-routing.ts` | [export const ROOM_ROUTING_TIMEOUT_MS](../../personal-agent/OpenMausBot/server/decider/room-routing.ts#L4)；[export const ROOM_ROUTING_MIN_PROBABILITY](../../personal-agent/OpenMausBot/server/decider/room-routing.ts#L6) |
| `server/graceful-shutdown.ts` | [export function createGracefulShutdown](../../personal-agent/OpenMausBot/server/graceful-shutdown.ts#L8) |
| `src/state/store.tsx` | [// Hydrate only after the stream](../../personal-agent/OpenMausBot/src/state/store.tsx#L3364) |
| `src/lib/live-events.ts` | [export function openLiveEvents](../../personal-agent/OpenMausBot/src/lib/live-events.ts#L162) |
| `server/fleet.ts` | [// Many client workspaces](../../personal-agent/OpenMausBot/server/fleet.ts#L1) |
| `server/sentinel/scan.ts` | [export function runScan](../../personal-agent/OpenMausBot/server/sentinel/scan.ts#L34) |
| `server/host/README.md` | [# server/host](../../personal-agent/OpenMausBot/server/host/README.md#L1) |
| `server/routes/README.md` | [# server/routes](../../personal-agent/OpenMausBot/server/routes/README.md#L1) |
| `docs/verification/README.md` | [# Verifying OpenMausBot](../../personal-agent/OpenMausBot/docs/verification/README.md#L1) |
