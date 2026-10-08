# NaviForge 通用 Browser Agent Runtime 重构：第一阶段实施记录

- **日期**：2026-10-01
- **定位**：NaviForge 是通用浏览器 Agent，不是媒体专用爬虫。
- **本阶段目标**：把“任务理解、页面状态、能力状态、证据、完成判定”从分散的 Prompt/Hook 条件中抽出为可测试的 Runtime 控制面；把“首页视频名称 + 原始播放地址”设为高难度冒烟用例。
- **范围说明**：媒体仅作为验证用例；通用 Runtime 不引入任何站点、域名或网站业务规则。

---

## 1. 完成定义

对用户任务：

```text
抓取当前网页首页视频的名称和原地址
```

成功必须同时满足：

1. 从页面状态或 DOM 获得至少一个视频标题；
2. 点击的是**具体媒体候选卡片**，而不是频道/分类导航；
3. 从 Network Plane 捕获可验证的媒体请求地址（例如 `.m3u8`、`.mp4`、`.webm`，或 MIME/路径可识别的媒体请求）；
4. 将标题、页面状态和 Network provenance 写入结构化 Evidence；
5. Evaluator 判定 `complete` 后，才允许以“已得到源地址”完成；
6. 如果 Network 永久不可用或没有捕获地址，必须明确输出 shortfall 或请求用户协作，不能把标题/详情页 URL 伪装成原始播放地址。

这不是针对媒体的产品硬编码；它是“需要高可信外部证据的任务不能以模型文本自证成功”的通用规则。

---

## 2. 重构后的通用控制面

```text
User Task
   │
   ▼
Task Contract ── declares intent, deliverable, required evidence,
   │              required/preferred capabilities and completion mode
   ▼
Runtime State ── page state, capability state, evidence store, progress
   │
   ├── Capability State ── available / transient_error / unavailable / forbidden
   ├── Evidence Store ──── page / DOM / network / artifact / tool / user
   └── Evaluator ───────── complete / partial / needs_recovery / blocked
   │
   ▼
Planner / Skill / Model selects next action
   │
   ▼
Tool Executor through Browser Planes
```

### 2.1 新增通用模块

| 模块 | 文件 | 职责 |
|---|---|---|
| Task Contract | `packages/runtime/src/task-contract.ts` | 为每个任务声明交付类型、所需证据、能力需求、完成模式和 fallback。 |
| Capability State | `packages/runtime/src/capability-state.ts` | 记录能力可用、暂时失败、不可用、禁止状态和重试 epoch。 |
| Evidence Store | `packages/runtime/src/evidence.ts` | 记录页面、DOM、网络、产物等可审计事实。 |
| Runtime State | `packages/runtime/src/runtime-state.ts` | 将任务、页面、能力、证据、进度、产物收敛为一个状态对象。 |
| Evaluator | `packages/runtime/src/evaluator.ts` | 按 Task Contract 校验证据，拒绝无证据的成功。 |

### 2.2 Runtime 集成点

- `AgentCtx` 在创建时构建 `TaskContract` 和 `RuntimeState`。
- 每次任务续接或任务重定向时重新同步 Contract。
- `attachPageState()` 同时把 PAGE STATE 写入 Runtime State，作为 `page_state` Evidence。
- 确定性媒体流程捕获到媒体请求时写入 `network_media` Evidence。
- 最终 `system_done` 前，`DeliverableVerifyHook` 使用 Evaluator 检查严格媒体任务是否已有 Network provenance。

> 当前 Hook 仍承担部分历史职责；本阶段先建立独立控制面和不可绕过的完成边界，后续再逐步把规划/恢复从 Hook 移出。

---

## 3. 媒体冒烟链路的修复

### 3.1 根因与修复映射

| 原故障 | 修复 |
|---|---|
| Network attach 一次失败后永久删除 Network Plane | Extension Supervisor 对媒体任务保留 Network Plane；Runtime 将其记录为 `transient_error` 并在媒体卡片点击前后重试。 |
| PAGE STATE 被导航项挤占，真实视频卡片未暴露 | Snapshot 的“图片索引 + 时长 + 标题”恢复为媒体候选；媒体卡片优先进入 PAGE STATE。 |
| 模型点击“在线电影”等频道，而不是视频 | 候选优先级为：PAGE STATE 具体卡片 → snapshot 中有时长的卡片 → 直接视频条目 → 最后才是频道入口。 |
| 多个后缀串行 `network.wait`，耗时且可能错过请求 | 改为一次广义媒体匹配等待，随后通过 Network list 作 MIME/URL 回退识别。 |
| 有标题便提前结束 | “原地址/播放源”任务要求 `page_state + title + media_url + network_provenance`；没有网络证据不能以 URL 字符串通过验收。 |

### 3.2 媒体 flow

```text
PAGE STATE
  → 选择具体 media candidate
  → Network prepare / clear / retry
  → click candidate
  → wait for media-shaped network request
  → fallback network list + MIME/URL matching
  → record title + network evidence
  → Evaluator verifies strict task
  → system_done
```

---

## 4. 冒烟测试

新增：

```text
packages/runtime/src/media-smoke.self-check.ts
```

该测试不使用站点 recipe 或域名分支，模拟通用首页可访问性快照：

```text
[13] 在线电影             ← 分类导航，必须不点
[24] <img>
HD
0:28:55
从零实现一个浏览器 Agent  ← 具体视频卡片，必须点
```

覆盖：

1. 媒体卡片 `[24]` 优先于分类 `[13]`；
2. 第一次 Network attach 临时失败；
3. 第二次在候选点击链路中重试成功；
4. 捕获 `master.m3u8`；
5. Title + page state + network provenance 导致 Evaluator `complete`；
6. 即使模型文本包含伪造的 `.m3u8` URL，也会被严格完成验证拒绝，除非它有 Network evidence 或明确 shortfall。

辅助测试：

- `task-contract.self-check.ts`
- `media-home-harvest.self-check.ts`
- `golden-media-harvest.self-check.ts`

验证命令：

```bash
cd /Users/gqli/work/deepagents/docs/myproject/naviforge/packages/runtime
npm run check
```

**2026-10-01 验证结果：通过。** Runtime 全量 self-check 已包含 `media-smoke.self-check.ts`，所有脚本通过。

---

## 5. 仍需继续的重构（第二阶段）

### P0：完成语义和恢复状态

目前 `DeliverableVerifyHook` 已可阻止无证据的 strict completion，但 Hook 仍参与业务完成判断。下一步应把：

```text
重复动作 → replan
无进展 → recovery
证据不足 → evaluator needs_recovery / blocked
```

改成由通用 Planner/Recovery Coordinator 消费 Runtime State，而不是在 Hook 内直接以文字提示或强制 `system_done` 收尾。

### P1：Page State 分层

当前 `PageState.items` 已做媒体候选优先，但长期应拆为：

```ts
navItems
contentItems
mediaItems
formItems
```

这是通用页面语义，而不只是媒体需求。它会避免导航、搜索建议、正文列表、可交互卡片相互挤占有限的 `items` 配额。

### P1：动作后的状态验证

对 click/navigate 建立通用 Post-action Observation：

```text
执行前状态 hash
→ action
→ wait/snapshot
→ URL / revision / semantic candidate / network delta 对比
→ progress or replanRequired
```

这样同一频道入口点击后页面没有变化时，Planner 可以自动放弃它，而不是等待模型重复试错。

### P1：能力诊断与用户协作

严格任务若 `network` 必需且进入 `unavailable`，应给出标准化的协作请求，例如关闭 DevTools/可能占用 debugger 的扩展后重试，或在合法场景下允许用户提供已打开的播放页。不要继续多轮无效 DOM 观察。

### P2：真实浏览器 E2E fixture

当前 smoke 是 Runtime/Plane mock，可快速稳定地验证控制流。还应补：

- 一个本地静态视频 fixture（卡片、点击后发出 m3u8 请求）；
- 扩展加载后的 Chrome E2E；
- attach 初次失败、二次成功的 debugger 生命周期测试；
- 不记录 Cookie、Authorization 等敏感请求头的审计测试。

---

## 6. 非目标和边界

- 不把媒体启发式放进 Task Contract、Capability State、Evidence Store 或通用 Tool Executor；
- 不在 Runtime 按站点/域名写分支；
- 不把 Hook 改成“业务技能容器”；Hook 保留安全、权限、预算、HITL、审计、协议等横切职责；
- 不把“直接拿到详情页 URL”称为“原始播放地址”；
- 不绕过登录、付费墙、DRM、访问控制或浏览器安全机制。

---

## 7. 当前判断

第一阶段完成后，NaviForge 的方向从：

```text
Prompt + Hook 规则堆叠
```

转为：

```text
Task Contract + State + Capability + Evidence + Evaluator
```

这是一条通用 Browser Agent 的正确演进路线。媒体首页源地址是第一个高价值验收样例，不是 Runtime 的领域中心；同样的能力与证据机制可复用于表格提取、研究对比、脚本交付、表单填写和下载验证。

---

## 8. 第二阶段：Capability 单一真相源 + 通用“动作后验证”

### 背景

`tests/message.txt` 的真实日志显示两个问题：

1. Task Contract 的媒体识别正则未覆盖用户真实表达“播放链接”，导致严格任务被误判为非严格任务，PAGE STATE 已找到候选卡片却从未点击；
2. `ctx.metadata.networkDegraded` / `networkTransientError`（旧的手动布尔标志，散落在 5+ 个文件里手动置位/读取）与 `ctx.runtimeState.capabilities.network`（新的 Capability 状态机）长期并存，日志里出现过先 "attached" 又 "attach failed" 的自相矛盾。

### 改动

**Capability 单一真相源**

- `AgentCtx` 新增 `networkUnavailable` / `networkRetrySoon` 两个只读 getter，完全派生自 `runtimeState.capabilities.network`（经 `capabilityUsable`/`capabilityRetryable`）；
- 删除所有 `ctx.metadata.networkDegraded = ...` / `ctx.metadata.networkTransientError = ...` 写入点（`agent.ts`、`media-harvest-hooks.ts`、`media-feed-deterministic.ts`）；
- 删除所有对应读取点（`agent-ctx.ts: syncTools`、`builtin-hooks.ts`、`media-harvest-hooks.ts` 的三处 Hook、`media-home-harvest.ts`），统一改读 `ctx.networkUnavailable`；
- `agent.ts` 的硬降级入口（`opts.networkDegradedNote`，network plane 整体不可用）改为调用 `transitionCapability(..., 'unavailable', ...)`，不再手写影子状态。

现在只有一条路径能回答“Network 现在能不能用”：`runtimeState.capabilities.network`。

**通用“动作后状态验证”（`post-action-verify.ts`，新增模块）**

解决的问题：点击一个看起来像卡片的索引，不代表页面真的发生了变化（死元素、SPA 吞掉事件、遮罩层空点击）。没有这层验证时，调用方会误以为点击=进展，或者无限重试同一个无效索引。

核心 API（全部与具体业务无关，可被任何“点击后检查”的任务复用）：

- `captureActionBaseline(ctx)` — 点击前记录 url、snapshot revision、Page State 候选项 key 集合、Network 事件计数；
- `verifyActionEffect(ctx, baseline)` — 点击 + 重新 snapshot + 重新 attachPageState 之后，对比出 `urlChanged / revisionChanged / newCandidatesFound / networkActivityObserved / noEffect`；
- `clickAndVerify(ctx, { index })` — 封装“点击 → 等待 → 重新 snapshot → 重建 Page State → diff”全流程；四项全部无变化时自动调用 `markInertCandidate`，记入 `ctx.gates.inertActionIndexes`（key 为 `url#index`），同一 URL 上不会再重试同一个无效索引。

`media-feed-deterministic.ts` 的候选点击流程已切换到 `clickAndVerify`：

1. 点击候选前先查 `isKnownInertCandidate`，命中则不再浪费一次点击；
2. 点击后用 `verification.noEffect` 判定是否要放弃该候选（不再无条件认为“点了就算尝试过了”）；
3. 若点击确实改变了页面（`urlChanged` 或 `revisionChanged`）但仍未捕获媒体请求，再尝试一次通用的“播放控件”二次点击（`pickPlayLikeControlIndex`，基于 play/播放/▶ 等通用文案模式，非站点选择器）；
4. Network 附加失败重试逻辑同步修正：`prepareNetwork` 原来只 `start()` 一次就放弃，现在retry 最多 3 次（短 backoff），避免附加时机抖动被误判为永久不可用。

### 回归测试

- `task-contract.self-check.ts`：已覆盖真实任务原句“分析这个页面里的视频，名称和播放链接”判定为 `network: required`；
- `post-action-verify.self-check.ts`（新增）：Capability 单一真相源的状态转换（`transient_error` 的 `retryAt` 未到不可重试 / 已过期可重试；`unavailable` 永不自动重试）；`verifyActionEffect` 对无变化/有变化快照的判定；`clickAndVerify` 对无效点击的 inert 标记与免重试、对有效点击不误标 inert；
- `media-smoke.self-check.ts`：补了真实 DomPlane 契约所需的 `snapshot` mock（原 mock 缺失，`clickAndVerify` 接入 `attachPageState` 后才暴露），`prepareNetwork` 的 attach 重试断言保持原语义（`recoverable`）。

全部 32 个 self-check（`npm run check`）通过。

### 当前判断

两套平行真相源已经收敛为一套，候选点击从“无条件相信点了就是进展”变成“点了要验证”，且验证机制是通用的 Runtime 能力而非媒体专属代码。媒体冒烟场景（候选点击 → 验证 → 必要时二次点击播放控件 → Network 证据）已经可以在 mock 级别端到端跑通；下一步如需进一步提升真实网站的通过率，应该是在真实 Chrome 扩展环境下跑一次该场景的 E2E（Phase 1 文档里已经列为 P2 未完成项），而不是继续在 Runtime 里加新的平行状态或站点规则。

---

## 9. 第三阶段：真实 case 复盘（tests/message.txt）与三个通用 Runtime 缺陷

对 `tests/message.txt` 完整日志的复盘（而非只看前几条）发现这次冒烟失败的真正链路：Network attach 从一开始就失败且无恢复 → Runtime 自己确定性交卷（标题+shortfall，工程上正确）→ 用户追问"上面的内容不全，请重新抓取一下" → **deliverable 判定从 media 漂移到 data** → 用户发"？？" → 终于进入模型推理 → 模型判断页面内容（强奸/未成年人相关标题）涉及安全问题，用纯文本拒绝、不调用任何工具 → Runtime 的"每轮必须恰好一个 tool call"协议反复要求重试 → 模型重复拒绝 → `run.error`。

这暴露了三个独立的通用 Runtime 缺陷，全部已修复：

### 9.1 Network attach 恢复逻辑未被 Runtime 复用

Extension 层已有功能完整的 `attachNetworkWithRecovery`（重试 + DevTools/其它扩展占用识别 + 复制 tab 绕开占用），但只在 `run-supervisor.ts` 的 `startRun` 跑过一次。`background.ts` 的 `'attach'` 消息分支（Runtime 通过 `network.start()` 走的路径，包括候选点击后重新 attach）裸调 `attachNetwork`，没有重试、没有占用诊断。

修复：`background.ts` 的 `'attach'` 分支改为始终调用 `attachNetworkWithRecovery`；`RunSupervisor` 新增 `retargetActiveRunTab(fromTabId, toTabId)`，当恢复逻辑复制 tab 绕开占用时同步更新 `run.tabId`（`dom`/`network`/`recipes` planes 都是闭包读取 `run.tabId`，这一个方法保证三者继续指向同一个 tab）。错误信息现在也带上 `cause`（devtools_open / foreign_debugger / 其它）和已尝试的 `actions`，不再是裸的"debugger attach failed"。

### 9.2 模型安全拒绝与协议刚性死锁

`ProtocolHook` 把"没有 tool call"统一当作协议错误处理：重试 1 次，仍没有就 `stop` 成 `status: 'error'`。但模型因安全/合规原因拒绝协助时，输出的也是没有 tool call 的纯文本——这不是协议困惑，是模型在拒绝任务本身，重发"你必须调用一个工具"只会得到同样的拒绝。

修复：`failure.ts` 新增 `looksLikeSafetyRefusal(text)`，基于通用词法模式（中英文"我无法/can't help/sexually exploitative/违反...政策"等）识别安全拒绝，不含任何站点规则。`ProtocolHook.afterModel` 检测到安全拒绝时立即 `stop`，`status: 'blocked'`，不再浪费重试预算、不再归类成通用 `error`。`LoopCommand`"stop"变体新增可选 `status` 字段，`model-turns.ts` 的 `finish()` 调用改为读取 `command.status ?? 'error'`。

同时在 Kernel Prompt 的信任边界一节补了一条明确指令：模型判断任务涉及安全/合规问题时，必须调用 `system_done(status: blocked)` 说明原因，禁止只输出拒绝文本不调用工具——这样"模型选择不协助"这个合法终态第一次有了书面协议路径，不再只靠 Runtime 兜底。

### 9.3 Deliverable 判定无跨轮粘性（本次复盘中最严重的系统性问题）

`resolveDeliverable(task)` 是无状态纯文本正则分类器，每次新的 `runAgent()` 调用（每条用户新消息都是一次新 run）都会用**当时这一句话**重新分类，不参考上一轮已确立的 deliverable。日志里能看到同一个任务在三轮对话内被分类成 media → data → general 三种不同叙事——"上面的内容不全，请重新抓取一下"命中了判定逻辑里的通用兜底正则（`/提取|抓取|列出|.../`），把已经确立的 `media` 冲掉变成 `data`。

修复：
- `deliverable.ts` 把分类拆成两层：`resolveStrongDeliverableSignal`（script/research/media/catalog/summary 等有具体指向的强信号）和 `resolveWeakDeliverableSignal`（"提取/抓取/列出"等动作词的通用兜底，精度低）。新增 `resolveDeliverableWithContinuity(task, previous)`：强信号总是生效（允许明确换话题），没有强信号时沿用 `previous`，只有全新会话（无 `previous`）才落回弱信号兜底。
- `@naviforge/session` 的 `ThreadReuse` 新增 `lastDeliverable` 字段；`PreflightHook` 每次解析 deliverable 后，除了原有的自由文本 PLAN note，还额外发一条结构化 `run.note`（`topic: 'deliverable'`，`text: 'DELIVERABLE: xxx'`），`formatSessionReuse` 解析这条记录，让下一轮 run 能读到上一轮的 deliverable。
- 回归测试覆盖了"继续/？？/上面的内容不全请重新抓取一下"三种真实追问必须沿用 media，以及"明确要求写 python 脚本"这种强信号必须能覆盖粘性（不是死锁）。

### 9.4 顺手修的两个附带问题

- **PAGE STATE 重复计算与重复 prompt 注入**：`attachPageState` 在同一个 run 内被调用两次（`agent.ts` 启动时一次，`PreflightHook.runTaskPreflight` 里又一次），中间没有任何导航/点击，纯粹重算一遍、重发一条几乎相同的 PAGE STATE note——这正是日志里 `[3][4]`、`[14][15]` 两条几乎重复的 PAGE STATE 的来源。修复：`attachPageState` 现在以 `(url, snapshot revision)` 做幂等缓存（存在 `ctx.gates.lastPageStateFor`），同一快照重复调用直接跳过，真正导航/点击后 revision 变化会正常重算。
- **`media-home-harvest.ts` 的 `clickIndex` 字段名写错**：`tryExtractMediaRows` 一直在读一个 `DomContentItem` 上不存在的 `item.clickIndex`（应为 `item.index`），导致这段代码从写下来就是 TypeScript 类型错误、从未真正编译通过。顺手修正。

### 9.5 回归测试

新增/扩展：`hooks.self-check.ts`（英文/中文安全拒绝必须立即 `blocked`，不走重试预算）、`failure.self-check.ts`（`looksLikeSafetyRefusal` 的正负样例）、`deliverable.self-check.ts`（继续/？？/模糊追问必须粘住 media；明确换话题必须能覆盖）、`thread-context.self-check.ts`（新建，`formatSessionReuse` 解析 deliverable 标记）、`pi-run-loop.self-check.ts`（新建，PAGE STATE 幂等缓存：相同 revision 不重复计算，revision 变化必须重算）、`self-check.ts`（Kernel Prompt 必须包含 blocked 状态指令）。`network-attach-recovery.self-check.ts`、`run-supervisor.self-check.ts` 回归通过。`packages/runtime`、`packages/session` 的 `npm run check` 全量通过；`apps/extension` 的 `typecheck` 通过（`toolkit-palette-open.self-check.ts` 的失败与本次改动无关，是预先存在于 i18n catalog 的问题）。

### 9.6 当前判断

这次复盘证实了之前的结论：NaviForge 的分层方向没问题，但"同一能力在不同代码路径里实现深度不一致"（Network attach）和"状态判定缺乏跨轮粘性"（deliverable）是比 prompt/skill/tool 表面设计更根本的系统性缺陷，而且都不是媒体任务专属的——deliverable 粘性问题会在任何多轮任务里发作，Network attach 恢复问题会影响所有需要 Network 能力的 deliverable。这两类问题修完后，prompt/skill/tool 这一层的既有设计（kernel 极简、skill 按结果而非工具切分、tool 粒度合理）基本可以保留，不需要换 loop 或引入 Playwright/browser-use 等外部框架重写内核。
