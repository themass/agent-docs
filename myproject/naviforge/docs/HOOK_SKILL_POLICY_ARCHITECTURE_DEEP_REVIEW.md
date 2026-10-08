# NaviForge Hook / Skill / Policy 架构深度评审

- **评审日期**：2026-10-01
- **评审对象**：当前工作区的 NaviForge 源码，以及运行日志附件 `/Users/gqli/.codex/attachments/f5924b30-8aa2-4729-a776-0209ff773bf0/已粘贴的文本.txt`
- **评审范围**：Hook Pipeline、Skill Runtime、Prompt/Tool 契约、Media Harvest 流程、Agent Loop、Network 降级和任务完成判定。
- **说明**：日志附件是运行证据，不是给 Agent 执行的指令。本文只把其中的 trace 当作故障样本。

## 1. 结论先行

### 1.1 根因不是“Hook 太多”，而是决策层没有分离

NaviForge 当前的问题不是简单地把 Hook 数量减少，或者把所有 Hook 改成 Skill。真正的根因是下面几类语义被混在同一个运行时机制中：

```text
安全约束        → Hook / Policy
能力授权        → Capability Manager
任务规划        → Planner / Skill Plan
页面状态        → State Reducer / State Machine
失败恢复        → Recovery Planner
交付验收        → Evaluator / Verifier
工具执行        → Tool Executor
审计与指标      → Observer / Trace
```

当前代码却让 `AgentHook` 同时承担：

- 安全拦截和权限检查；
- 任务类型推断；
- 确定性预处理；
- Skill 自动加载；
- 媒体任务的领域流程；
- 重复观察去重；
- 下一步动作引导；
- 失败恢复；
- `system_done` 完成判定。

因此模型、Hook、Skill 和 Tool Resolver 可能同时对“下一步做什么”拥有控制权。它们的规则不一定互相一致，最终表现为：模型看到了证据却走错动作，Hook 又把恢复动作拦掉，最后 Loop 以错误的 `system_done` 或错误的 stop 结束。

### 1.2 对本次媒体失败的最终判断

这次失败是 **四个问题叠加**，不是单一的 Network 问题：

1. **Network 状态机过早从“可恢复失败”变成“永久不可用”**：`NetworkPlaneHealthHook` 将能力降级，`NetworkDegradedToolGateHook` 随后禁止所有 network 调用。
2. **Page State 丢失了真正的视频卡片**：日志里的 `dom_snapshot` 已经有视频标题、时长和卡片索引，但 PAGE STATE 只暴露了导航分类索引 10–15；模型因此不断点击“在线电影”分类 `index=13`。
3. **媒体流程被拆散在多个 Hook 中**：`PreflightHook`、`MediaHarvestMilestoneHook`、`DedupeObservationHook`、`ActionLoopHook` 和 `DeliverableVerifyHook` 分别对同一个任务做计划、阻断和完成判断，缺少一个显式的 Media Task State Machine。
4. **Tool 契约仍有漂移风险**：trace 中模型调用 `browser_observe(action=js, expression=...)`，最终内部执行报 `code required`。当前源码已有兼容转换，但公共 Schema 同时暴露 `code` 和 `expression`，且历史/构建版本之间存在不一致，这说明 Tool Contract 没有真正单一化。

### 1.3 总体评分建议

之前从平台完整性角度给 NaviForge 约 **7.6 / 10** 是合理的；但从“真实任务可靠完成”角度，本次证据显示需要拆分评分：

| 维度 | 当前评分 | 结论 |
|---|---:|---|
| 浏览器基础设施与 Plane 抽象 | 8.5 | DOM、Tabs、Network、Workspace、Trace 基础扎实 |
| Prompt / Context 工程 | 7.5 | 分层、Working Set、证据投影较好，但 Kernel 过载 |
| Tool API 契约 | 6.5 | 公共工具已经收敛，但参数别名和内部原子工具仍有漂移 |
| Skill 体系 | 6.5 | 有 L1/L2、路由和权限，但更像 Prompt 包，不是可执行能力包 |
| Hook / Policy 边界 | 5.5 | 约束、规划、恢复、验收混在 Hook 生命周期里 |
| Media Harvest 可靠性 | 4.5 | 对真实 SPA/视频首页的状态识别和恢复不足 |
| 完成判定与证据验证 | 5.5 | 主要靠文本和 Regex，缺少结构化 Evidence Contract |
| **综合工程成熟度** | **7.0 左右** | 不需要重写，但必须做控制平面重构 |

**判断：不建议推倒重写；建议优先重构决策边界。**

---

## 1.4 首先明确产品目标：通用浏览器 Agent

NaviForge 的目标不是“媒体抓取 Agent”，也不是“网页采集器”。目标应明确为：

> **在用户真实浏览器中，针对开放式网页任务，安全、可恢复、可验证地完成观察、导航、研究、提取、填写、交互和产物沉淀。**

媒体抓取只是一个高难度验证场景，用来暴露通用 Runtime 的缺陷。它不是核心架构的中心。

### 通用 Agent 的核心能力域

```text
Observe      当前页面、DOM、可访问性树、截图、网络证据
Navigate     标签、站内导航、分页、详情页、返回和范围控制
Research     搜索、多页面、多来源、只读并行
Extract      文本、列表、表格、媒体、结构化字段
Interact     点击、输入、选择、拖拽、等待、上传
Friction     登录、验证码、限频、付费墙、权限确认
Persist      下载、PDF、脚本、Workspace 产物
Verify       证据完整性、字段一致性、任务完成判断
Recover      重试、换路径、询问用户、部分交付和安全停止
```

### 通用层与领域层必须分开

| 层次 | 通用性要求 | 允许出现的媒体逻辑 |
|---|---|---|
| Runtime / Hook / Policy | 必须完全通用 | 不允许写媒体字段或媒体页面判断 |
| Task Contract | 通用结构，按任务声明差异 | 可以声明 `media_url` 这种任务字段 |
| Planner / Recovery | 通用机制，可接受 Skill 提供的候选计划 | 不应硬编码某个站点或固定索引 |
| Skill | 可插拔领域 SOP | 媒体 Skill 可以处理标题、播放器、HLS |
| Evaluator | 通用接口，领域提供验收规则 | 媒体 Skill 可以要求 media provenance |
| Test Fixture | 可以领域化 | 媒体场景作为高难度回归样本 |

因此，前面建议的 `Media Harvest v2` 应被理解为：

```text
通用 Runtime 架构
  + 一个 Media Skill / Media Evaluator 的垂直验证实现
```

而不是把 NaviForge 重构成媒体专用 Agent。

### 对下一步优化方向的修正

下一步真正应该建设的是通用的：

```text
Generic Task Contract
Generic Runtime State
Generic Capability Manager
Generic Planner / Recovery Planner 接口
Generic Evaluator 接口
```

然后使用媒体任务作为第一个端到端验收样本。后续应使用同一套内核验证：

- 页面摘要；
- 列表抽取；
- 列表到详情页；
- 多来源研究；
- 表单填写；
- 文件下载；
- 脚本生成；
- 媒体源提取。

如果新增一个 `media` 场景必须修改通用 Hook，说明架构仍然没有达到通用 Agent 的目标。

## 2. 运行日志还原：失败发生在哪里

### 2.1 关键 trace 链路

从附件 trace 可以还原出如下过程：

```text
PAGE STATE: home/list
  └─ 只暴露“精品推荐/官方推荐/在线电影”等分类 index

Network debugger attach failed
  └─ 运行时写入“DOM-only”计划
  └─ network 工具被禁止

structured extract
  └─ dom_extract_content 返回 3 个导航项，不是视频卡片
  └─ system_extract_page 返回 count=0

browser_observe(action=js)
  └─ 内部结果：code required
  └─ 没有形成有效的页面探测证据

browser_act(click index=13)
  └─ 点击的是“在线电影”分类，不是视频卡片
  └─ URL 没有改变，页面仍是 home

browser_observe(snapshot) × 多次
  └─ snapshot 实际包含大量视频标题和时长
  └─ PAGE STATE 仍只暴露分类

DedupeObservation / ActionLoop
  └─ 阻止继续 snapshot/click
  └─ 提示使用现有产物或 system_done

Deliverable / Protocol
  └─ 模型先生成无工具调用的失败结论
  └─ 最终 system_done：未找到视频名称和源地址
```

### 2.2 最重要的矛盾：系统已经拿到了证据，但证据没有进入可决策状态

日志第 51/56/61/78 附近的 snapshot 内容中已经出现：

- `今日热播`；
- `HD`；
- `0:28:55`；
- 视频标题；
- `猫咪官方`；
- 播放量；
- `[20]`、`[22]`、`[24]` 等卡片相关索引。

但 PAGE STATE 只给模型：

```text
<div >精品推荐 click_index=10
<div >官方推荐 click_index=11
<div >另类色情 click_index=12
<div >在线电影 click_index=13
```

这不是“模型能力不够”，而是 **State Projection 错误**：运行时把低价值的导航节点投影给了模型，却没有把高价值、可执行的媒体卡片投影给模型。

之后模型点击 `index=13` 是符合当前 PAGE STATE 的理性行为。真正的问题是：

```text
snapshot → Page State 的转换器没有把媒体卡片识别成 actionable items
```

当前工作区已经加入 `extractIndexedMediaCards()` 和 snapshot feed 合并逻辑，这是正确方向；但必须通过真实 trace 回归确认：

1. 运行时使用的是包含该逻辑的构建产物；
2. `attachPageState()` 在每次 snapshot refresh 后重新生成 Page State；
3. media card 的 `clickIndex` 与当前 snapshot revision 一致；
4. Page State 的排序不会再次被导航项挤掉前 12 项。

### 2.3 Network 失败不应该等于任务能力永久消失

当前降级逻辑位于：

- `/Users/gqli/work/deepagents/docs/myproject/naviforge/packages/runtime/src/media-harvest-hooks.ts`
- `/Users/gqli/work/deepagents/docs/myproject/naviforge/apps/extension/src/lib/run-supervisor.ts`

`markNetworkDegraded()` 做了三件事：

```ts
ctx.metadata.networkDegraded = true
ctx.agent.planes.network = undefined
ctx.networkText = 'NETWORK: (degraded — DOM-only for this run)'
```

随后 `NetworkDegradedToolGateHook` 直接拦截 network 工具。

这在“能力确实不存在”时是合理的安全保护，但在 debugger attach 失败时不合理，因为 attach 失败可能是：

- readiness probe 释放了 debugger；
- tab 切换导致绑定过期；
- Chrome debugger 短暂竞争；
- 页面尚未稳定；
- 第一次 start 失败但第二次可以成功。

所以这里需要区分三种状态：

```ts
type NetworkStatus =
  | { kind: 'available'; lastHealthyAt: number }
  | { kind: 'starting'; attempts: number }
  | { kind: 'transient_error'; retryAt: number; attempts: number; reason: string }
  | { kind: 'unavailable'; reason: string; retryable: boolean }
  | { kind: 'forbidden'; reason: string }
```

只有 `forbidden` 或经过恢复预算耗尽的 `unavailable` 才应该从能力表中移除。`transient_error` 不能让 Hook 永久锁死能力。

---

## 3. Hook、Skill、Policy、Planner 的职责边界

### 3.1 推荐职责矩阵

| 组件 | 应负责 | 不应负责 |
|---|---|---|
| **Hook** | 不可违背的运行时约束、生命周期审计、超时、取消、scope、HITL 闸门、工具 schema 保护 | 决定业务下一步、替 Skill 选择媒体卡片、暗中规划恢复流程 |
| **Skill** | 领域 SOP、工具使用顺序建议、证据字段、完成条件、领域恢复策略 | 全局安全策略、篡改 Plane 状态、绕过权限、直接终止任意任务 |
| **Policy** | 工具/能力授权、风险等级、是否需要确认、navigation scope、网络/脚本/写入权限 | 领域流程和页面语义 |
| **Planner** | 根据 Task Contract、State 和 Evidence 选择下一步动作 | 直接绕过 Capability Policy 或直接执行 Chrome I/O |
| **Capability Manager** | 声明能力状态、重试、降级、恢复预算、能力授予/撤销 | 决定用户任务的业务目标 |
| **State Reducer** | 将工具结果转为 Page/Network/Task 状态，保证状态转换可追踪 | 生成自然语言计划 |
| **Recovery Planner** | 失败后的替代路径：重试、换观测、点击卡片、询问用户、短缺输出 | 全局安全审批 |
| **Evaluator / Verifier** | 判断证据是否满足交付契约，判断是否可完成 | 执行工具、代替模型规划 |
| **Runtime** | 调度模型、执行工具、应用状态转换、记录 trace | 把每种领域流程硬编码成 Hook |

### 3.2 最关键的规则

> **只有一个地方可以决定“下一步动作”：Planner。**

Hook 可以说：

- “这个动作不允许”；
- “这个参数不合法”；
- “需要用户确认”；
- “这个能力当前不可用”；
- “必须重新规划”。

Hook 不应该说：

- “下一步必须 system_done”；
- “点击这个固定 index”；
- “用已有产物结束”；
- “不要再观察，直接输出缺失”。

后一组属于 Planner、Recovery Planner 或 Evaluator 的职责。当前 `DedupeObservationHook` 和 `ActionLoopHook` 已经越过了这条边界。

---

## 4. 对当前 Hook Pipeline 的逐个判断

### 4.1 `NetworkPlaneHealthHook`

**当前职责**：在 `runTaskPreflight` 中检测 Network digest，尝试 `start()`，失败后降级。

**判断**：健康探测放在生命周期 Hook 合适；但“永久删除 Network Plane”和“改变任务计划”不合适。

**应重构为**：

```text
NetworkHealthObserver（读取健康状态）
  → CapabilityManager（更新 available/transient/unavailable）
  → RecoveryPlanner（决定 retry / DOM fallback / ask_user）
```

Hook 只负责把健康状态写入上下文，并阻止明显不安全的调用。不要直接把 `ctx.agent.planes.network` 设为 `undefined`。

### 4.2 `PreflightHook`

**当前职责**：deliverable/intent 推断、recipe、媒体确定性采集、Skill 加载、列表读取、page read、friction、catalog 预处理。

**判断**：这是当前最大的问题。它不是 Hook，而是一个“隐式任务执行器”。

**建议拆分**：

```text
TaskContractBuilder
DeterministicProbeRunner
SkillBootstrapper
RecipeRunner
InitialEvidenceCollector
```

`runTaskPreflight` 只返回结构化的 `PreflightResult`，不要返回一段可以直接交卷的字符串：

```ts
type PreflightResult = {
  contract: TaskContract
  evidence: Evidence[]
  state: RuntimeState
  suggestedPlan?: Plan
  next?: 'model' | 'done' | 'ask_user' | 'recover'
}
```

### 4.3 `NetworkDegradedToolGateHook`

**当前职责**：一旦 `networkDegraded`，所有 network 工具都 skip。

**判断**：作为 Policy Gate 可以存在，但当前是永久锁死，不适合恢复型 Agent。

**建议**：根据能力状态决定：

- `transient_error`：允许一次 retry 或安排 backoff；
- `unavailable`：禁止直接调用，但允许 Capability Manager 重新 attach；
- `forbidden`：硬拦截；
- `dom_fallback`：只允许 DOM 路径，并明确交付为 partial/shortfall。

不要只用 `boolean networkDegraded` 表示所有网络状态。

### 4.4 `MediaHarvestMilestoneHook`

**当前职责**：发现 snapshot 中有媒体标题后，向模型写入“点击详情/读取 network”，并禁止重复 passive observe。

**判断**：这不是通用 Hook，是媒体领域的 `MediaEvaluator + MediaRecoveryPlanner`。

**建议**：移动到 `media` Skill 的执行计划中。通用 Runtime 只接收：

```ts
skill.evaluate(state) ->
  | { status: 'need_action'; candidates: CandidateAction[] }
  | { status: 'partial'; shortfall: Shortfall }
  | { status: 'complete'; evidence: Evidence[] }
```

媒体 Skill 可以识别“标题 + 时长 + 卡片 index”是媒体卡片，但全局 Hook 不应该知道这些页面语义。

### 4.5 `DedupeObservationHook`

**当前职责**：同一 URL/同一观察重复时 skip；重复次数达到阈值后建议 `system_done` 或直接 stop。

**判断**：去重本身属于 Runtime Guard；“因此必须结束”属于错误的控制权扩张。

**问题**：同一个 `dom_snapshot` 重复执行可能确实无意义，但如果页面状态发生了 revision、网络事件发生了变化、用户刚刚点击了播放器，旧 observation key 就不应继续生效。

**建议**：dedupe key 必须至少包含：

```text
url + tabId + snapshotRevision + observationKind + relevantArguments + capabilityEpoch
```

去重结果应该是：

```text
DUPLICATE_OBSERVATION → Planner 重新规划
```

而不是：

```text
DUPLICATE_OBSERVATION → system_done
```

### 4.6 `ActionLoopHook`

**当前职责**：同一动作达到次数后 skip 或 stop，并提示使用现有产物/system_done。

**判断**：保留为安全护栏，但不能负责任务终止。

**建议**：返回结构化事件：

```ts
{ kind: 'guard_blocked', reason: 'same_action_limit', replanRequired: true }
```

将 `stopResult` 删除或只允许 Runtime 在“确实违反硬预算”时使用。动作循环和业务失败不是一回事。

### 4.7 `NoProgressHook`

**当前职责**：连续四步没有新证据就 `stop(status='error')`，并引导 `system_done`。

**判断**：这是一个粗粒度 termination heuristic，不能充当完成判定。

**问题**：媒体播放 URL 可能需要“点击 → 等待 → network wait”，中间几步不产生 DOM 新证据，但实际上在产生 network evidence。`stepsWithoutNewObs` 只看局部观察，可能误判“无进展”。

**建议**：进展应是多维的：

```ts
progress =
  newDomEvidence ||
  newNetworkEvidence ||
  stateTransition ||
  newCandidate ||
  userConfirmation ||
  artifactCreated
```

没有进展时进入 `RecoveryPlanner`，而不是直接 error。

### 4.8 `DeliverableVerifyHook`

**当前职责**：用 Regex 检查 `system_done.result` 是否包含 URL、`m3u8/mp4/media` 或 shortfall。

**判断**：验收职责应该保留，但不能基于自然语言 Regex。

**建议**：模型调用 `system_done` 时同时提交结构化交付：

```ts
type DeliverableSubmission = {
  status: 'complete' | 'partial' | 'blocked'
  records: Array<{
    title?: string
    pageUrl?: string
    mediaUrl?: string
    source: 'dom' | 'network' | 'fetch' | 'user'
    evidenceIds: string[]
  }>
  shortfall?: {
    code: string
    message: string
    attempted: string[]
  }
  summary: string
}
```

自然语言只用于展示；Evaluator 根据结构化字段验收。

### 4.9 `SkillAllowlistHook` 与 `RunProfileHook`

**判断**：两者都是 Policy/Capability Gate，不应与业务 Hook 混在同一组“流程 Hook”中。

建议建立单独的策略层：

```text
CapabilityPolicy
  = run profile ∩ skill requested capabilities ∩ user grants ∩ current plane status
```

并且输出结构化拒绝原因，不要只写一条自然语言 guidance。模型需要知道：

- 是 Skill 没有权限；
- 是 Run Profile 不允许；
- 是用户没有打开能力；
- 还是当前 Plane 暂时不可用。

### 4.10 `ToolStateHook`

**判断**：它其实是 State Reducer，不是 Hook。

它在 `afterTool` 中更新：

- list hints；
- loaded skills；
- script artifact；
- tab set；
- observation cache；
- steps without new observations；
- action loop state。

建议改成纯函数 reducer：

```ts
nextState = reduceRuntimeState(state, toolEvent)
```

这样可以做 replay、property test 和 trace 重建，避免 Hook 执行顺序改变时状态悄悄漂移。

---

## 5. Skill 现在有什么问题，是否应该把 Hook 改成 Skill

### 5.1 不能简单地“把 Hook 全改成 Skill”

直接把 Hook 改成 Skill 会造成另一种问题：

- 安全规则变成可被模型忽略的 Prompt；
- 能力撤销变成自然语言；
- `system_done` 验收被领域 Skill 自己放宽；
- 不同 Skill 之间互相覆盖权限；
- 页面污染内容可能伪装成 Skill 指令。

所以正确结论是：

```text
不是 Hook → Skill 的整体迁移。
而是把 Hook 中的“领域流程”迁移到 Skill，
把 Hook 中的“不可违背约束”留在 Policy/Runtime，
把 Hook 中的“完成判断”迁移到 Evaluator，
把 Hook 中的“失败恢复”迁移到 Recovery Planner。
```

### 5.2 当前 Skill 是 Prompt 包，还不是完整能力包

当前 `/Users/gqli/work/deepagents/docs/myproject/naviforge/packages/skill-runtime/src/index.ts` 的 Skill 主要包含：

- manifest；
- description/triggers；
- instructions；
- permissions；
- alias；
- L1/L2 渐进披露。

这套设计作为第一阶段是对的，但对专业 Browser Agent 不够。建议扩展为：

```ts
type ExecutableSkill = {
  manifest: {
    id: string
    version: string
    description: string
    triggers: string[]
    risk: 'read' | 'write' | 'external_write'
  }
  capabilities: CapabilityRequest[]
  instructions: string
  planTemplate: PlanTemplate
  stateTransitions: StateTransition[]
  evidenceRequirements: EvidenceRequirement[]
  completion: CompletionContract
  recovery: RecoveryStrategy[]
  limits: { maxSteps: number; maxRetries: number }
  verifier?: SkillVerifier
}
```

Skill 仍然不应该直接拿到 Chrome API；它只提供声明式计划、候选动作和验收规则。

### 5.3 推荐的 Media Skill

`harvest` 目前覆盖表单、媒体、比价等多个领域，职责过宽。建议至少拆出一个真正的媒体 Skill：

```text
media-harvest

目标：抽取当前页面视频条目及可验证播放源。

输入：当前 tab、Page State、DOM snapshot、Network capability。

证据要求：
- 视频标题；
- 卡片或详情页 URL；
- 播放源 URL（m3u8/mp4 等）及来源 network/dom；
- 无源时必须记录 shortfall code 和已尝试路径。

计划：
1. 识别 home/list/detail；
2. 优先读取结构化卡片；
3. 结构化为空时从 snapshot 恢复“图片/链接 + 时长 + 标题”卡片；
4. 选择真实 media candidate，不点击分类导航；
5. 点击卡片，等待页面/播放器/Network 状态转换；
6. 读取 network media/hls；
7. 校验 URL 不包含 cookie、Authorization 或一次性敏感凭证；
8. Evaluator 验收 complete/partial。

恢复：
- 卡片索引失效 → refresh snapshot；
- 当前仍是 home → 重新发现 media candidate；
- Network transient_error → retry attach；
- Network unavailable → 允许用户启用能力或输出 partial，不得伪装 complete；
- 需要登录/付费墙/DRM → friction/blocked shortfall，禁止绕过。
```

注意：该流程是 Skill/Planner 的领域 SOP，不应该继续堆到 `createRunHooks()` 中。

---

## 6. 推荐目标架构

### 6.1 目标流程

```text
User Task
   ↓
Task Classifier
   ↓
Task Contract Builder
   ↓
Skill Selector / Loader
   ↓
Planner
   ↓
Capability Manager + Policy Check
   ↓
Tool Executor
   ↓
State Reducer
   ↓
Evaluator
   ├─ complete → system_done
   ├─ partial  → partial result + shortfall
   ├─ recover  → Recovery Planner → Planner
   ├─ ask      → HITL
   └─ blocked  → blocked result
```

### 6.2 Hook Pipeline 的目标形态

保留的 Hook 只建议包括：

```text
RunLifecycleHook
SchemaValidationHook
ScopePolicyHook
CapabilityPolicyHook
Consent/HITLHook
Timeout/BudgetHook
PromptInjectionBoundaryHook
AuditTraceHook
```

移出 Hook Pipeline 的逻辑：

```text
Preflight 大流程        → Preflight Coordinator
媒体 milestone          → media-harvest Skill + Evaluator
页面列表识别            → State Reducer / Page State Extractor
动作重复与无进展        → Runtime Guard + Recovery Planner
交付 Regex              → Structured Evaluator
Skill 权限合并          → Capability Manager
ToolStateHook           → State Reducer
```

### 6.3 Task Contract

每个任务开始时先生成一个结构化 Contract，而不是只靠 `resolveDeliverable()` 和多条字符串 guidance：

```ts
type TaskContract = {
  intent: 'observe' | 'harvest' | 'traverse' | 'research' | 'persist'
  deliverable: 'summary' | 'data' | 'media' | 'script' | 'research'
  scope: { navigation: 'allowed' | 'forbidden'; anchorTabId?: number }
  requiredEvidence: string[]
  allowedFallbacks: string[]
  completion: 'strict' | 'partial_allowed'
  network: 'required' | 'preferred' | 'not_needed'
  maxRecoveryAttempts: number
}
```

本次媒体任务应明确：

```text
network = required/preferred（取决于用户是否要求播放源）
completion = strict if source URL required
requiredEvidence = title + source URL + provenance
allowedFallbacks = title/page URL + explicit shortfall
```

这样系统不会在 Network 不可用时仍然把“标题/页面链接”当成完成。

---

## 7. 建议的重构顺序

### P0：先修可靠性，不改大架构

1. **Page State 回归**：用真实 snapshot fixture 验证媒体卡片会进入 PAGE STATE，并且优先级高于分类节点。
2. **Tool Schema 单一化**：`browser_observe(action=js)` 只公开 `code`，`expression` 只作为内部一次性兼容迁移；Schema、resolver、handler、self-check 必须来自同一份定义。
3. **Network 状态分级**：去掉 `boolean networkDegraded` 的全局语义，至少区分 transient/unavailable/forbidden。
4. **禁止 Hook 直接结束业务任务**：`ActionLoopHook`、`DedupeObservationHook`、`NoProgressHook` 不再直接给 `system_done` 或错误 stop，改为 `replanRequired`。
5. **媒体任务真实回归**：至少覆盖：
   - home 有卡片；
   - structured extract 为空但 snapshot 有卡片；
   - 卡片 click 后仍在 home；
   - Network 第一次 attach 失败、第二次成功；
   - Network 永久不可用；
   - 详情页能捕获 m3u8/mp4；
   - 需要登录/付费墙/DRM。

### P1：重构控制平面

1. 新增 `TaskContract`；
2. 新增 `RuntimeState` 和纯 reducer；
3. 新增 `CapabilityManager`；
4. 新增 `Planner` / `RecoveryPlanner` 接口；
5. 将 `PreflightHook` 拆为协调器和若干纯/确定性步骤；
6. 将 `DeliverableVerifyHook` 改为结构化 `Evaluator`；
7. 将 `ToolStateHook` 改为 reducer，并保留 Hook 作为兼容适配层。

### P2：把 Skill 变成可执行声明

1. `harvest` 拆为 `media-harvest`、`form-harvest`、`price-harvest`；
2. Skill 增加 evidence/completion/recovery/limits；
3. 权限由 Capability Manager 合并，而不是 `routeSkills()` 直接决定最终 allowlist；
4. Skill 计划生成结构化候选动作，不直接写 `system_done` guidance；
5. 为每个 Skill 建立 golden traces 和离线 evaluator。

---

## 8. 需要新增的测试与评估指标

### 8.1 不应只测“工具是否调用成功”

建议增加任务级指标：

```text
Task Success Rate
Evidence Completeness
False Completion Rate
Recovery Success Rate
Capability Recovery Rate
Duplicate Action Rate
Wrong Candidate Click Rate
Time to First Valid Evidence
```

本次任务最关键的三个指标是：

- `Wrong Candidate Click Rate`：是否点击了分类而不是媒体卡片；
- `False Completion Rate`：没有 source evidence 却 system_done；
- `Recovery Success Rate`：Network 临时失败后是否能恢复。

### 8.2 Trace 应支持事件因果链

当前 trace 记录较多，但需要额外记录：

```text
decisionId
planId
contractId
capabilityEpoch
stateBefore/stateAfter
evidenceIds
blockedBy
replanReason
completionEvaluation
```

这样可以回答：

```text
为什么模型点击了 13？
是模型自己选的，还是 Page State 只给了 13？
为什么不能再 network？
是用户未授权、临时 attach 失败，还是 Policy 禁止？
为什么结束？
是 Evaluator 判定完成，还是 ActionLoopHook 触发 stop？
```

---

## 9. 最终评判

### 做得好的地方

- Browser Plane 抽象完整，DOM/Network/Tabs/Workspace 已经形成专业 Runtime 基础；
- Prompt 有分层和 Working Set，不是把所有内容塞进一个系统提示；
- Skill 已经有 L1/L2 渐进披露、版本和别名兼容意识；
- Tool 已经从大量原子函数收敛为少数模型面向的 meta tools；
- 有 Trace、Recovery、HITL、scope、URL drift 和权限控制，工程意识明显高于普通浏览器 Agent Demo；
- 当前对媒体首页增加 snapshot card recovery 和 Network attach retry，方向是正确的。

### 需要重点优化的地方

- Hook Pipeline 已经成为隐式业务编排器；
- `PreflightHook` 过重，既读页面又执行任务又加载 Skill；
- Skill 只有 instructions/permissions，缺少可执行计划、证据和恢复契约；
- Network 降级是布尔值和永久撤销，不支持恢复状态机；
- Page State 是决策关键，却没有被当作一级状态投影来测试；
- Dedupe/ActionLoop/NoProgress 把“防空转”错误地升级成“结束任务”；
- `system_done` 仍然依赖自然语言 Regex，而不是结构化交付；
- Tool Schema、Resolver、Handler 和历史构建产物存在漂移风险；
- 同一个任务的下一步可能由 Prompt、Skill、Hook、Tool Gate 四处同时决定。

### 最重要的重构原则

```text
减少 Hook 中的业务决策；
减少 Skill 中的全局安全逻辑；
让 Planner 成为唯一的下一步决策者；
让 Evaluator 成为唯一的完成判定者；
让 Capability Manager 成为唯一的能力授权者；
让 State Reducer 成为唯一的运行状态更新者。
```

**最终结论：NaviForge 不需要重写成“更多 Skill”，而需要重构成“Skill 驱动领域流程、Planner 做决策、Policy 管权限、Hook 做硬约束、Evaluator 做验收、State Machine 管状态”的浏览器 Agent Runtime。**
