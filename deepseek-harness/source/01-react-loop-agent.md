# 附录 A · `ReactLoopAgent` 源码走读

> 文件：`packages/core/agent-loop/src/agent.ts`  
> 读法：每段都是 **先白话 → 再代码 → 再注释 → 小节小结**；文末有总总结。  
> 术语不懂先查 [GLOSSARY.md](../GLOSSARY.md)。

### 本章你会搞懂什么

1. 用户点发送后，代码从哪进、怎么醒来  
2. 一轮 Turn 里 Step 怎么开、怎么停  
3. 模型请求怎么从 Session 日志「投影」出来  

---

## 0. 这个类在系统里干什么？

**白话**：`ReactLoopAgent` 是默认「司机」。工厂把它造出来，挂到某个 Session 上；以后所有 `followup` / 调模型 / 调工具，都是它在跑。

业务插件请依赖公开的 `Agent` 接口，**不要** import 本类私有方法。

### 代码：构造函数在装什么

```80:97:packages/core/agent-loop/src/agent.ts
  constructor(
    private loopCtx: Context,
    public readonly id: SessionId,
    public readonly options: AgentOptions,
    public readonly session: Session,
  ) {
    this.dispatch = agentEvents(loopCtx, this)
    this.inbox = new Inbox(session, {
      inserted: (message) => { this.dispatch.emit('agent/inbox/inserted', { message }) },
      discarded: (message) => { this.dispatch.emit('agent/inbox/discarded', { message }) },
      claimed: (message, turn) => { this.dispatch.emit('agent/inbox/claimed', { message, turn }) },
    })
    const lastTurn = session.events.findLast(event => event.type === 'turn/start')?.data.turn ?? 0
    this.phase = { kind: 'idle', lastTurn }
    this.scope = createScope(loopCtx, this)
    this.ctx = this.scope.ctx.extend({ agent: this })
    this.runtimeContext = new RuntimeContextProjection(this.ctx, session)
  }
```

### 注释（对着代码读）

| 行/片段 | 意思 |
|---------|------|
| `loopCtx` | 进程级挂架：上面有 `llm`、`tools`、`systemPrompt` |
| `session` | 这份对话的日志真源（只追加事件） |
| `dispatch` | 发 Agent 事件用的分发器（带好 initiator，热路径少分配） |
| `new Inbox(...)` | 收件箱：从会话里已有的 `agent/inbox/spliced` **回放**重建队列 |
| `inserted/discarded/claimed` | 队列变了就通知外面（UI/插件可听） |
| `lastTurn` | 恢复会话时从最后一条 `turn/start` 接着编号，避免从 0 重计 |
| `phase = idle` | 刚造出来时司机在休息 |
| `scope` / `ctx` | 按这个 Agent 隔离的挂架；工具可以只挂在「这个 Agent」上 |
| `runtimeContext` | 动态系统上下文投影（文件树变化等），后面 `preStep` 会用 |

### 本节小结

构造 = **装好 Inbox + 相位 + 作用域**。此时还没跟模型说话；要等 `followup` 才会醒。

---

## 1. 相位 `Phase`：司机三种姿态

**白话**：内部用三种状态描述「现在能不能开新活」。注意：`maintenance` 对外状态灯仍显示 idle（在做压缩等，不算正在跑 Turn）。

### 代码

```38:46:packages/core/agent-loop/src/agent.ts
type Phase =
  | { kind: 'idle'; lastTurn: number }
  | {
    kind: 'maintenance'
    abort: AbortController
    lastTurn: number
    wakeRequested: boolean
  }
  | { kind: 'running'; abort: AbortController; turn: number; step: number; wakeRequested: boolean }
```

### 注释

| kind | 人话 | `wakeRequested` 干嘛 |
|------|------|----------------------|
| `idle` | 没事干 | 无 |
| `maintenance` | 在做维护（如压缩），对外仍像空闲 | 维护结束后若为 true 且队列有货，再唤醒 |
| `running` | 正在跑 Turn | abort 途中有人又发消息，先记一笔，结束再醒 |

`setPhase`：**只有对外 status 真变了**才发 `agent/status`（maintenance↔idle 不刷 running）。

### 本节小结

相位管「能不能 kick」；`wakeRequested` 是「忙的时候来的唤醒，先记账，忙完再开」。

---

## 2. 入口：`followup` / `steer` / `inject`

**白话**：三种塞消息方式，差别只在「进哪个桶」和「要不要立刻叫醒司机」。

### 代码

```113:132:packages/core/agent-loop/src/agent.ts
  send(message: UserMessage, target: InboxTarget, wakeup: boolean): void {
    const wakingAfterAbort = wakeup && this.phase.kind !== 'idle' && this.phase.abort.signal.aborted
    const resolvedTarget = wakingAfterAbort ? 'next-turn' : target
    this.inbox.splice(resolvedTarget, Infinity, 0, [message])
    if (wakeup) this.wakeDriver(wakingAfterAbort)
  }

  followup(input: UserMessage): void {
    this.send(input, 'next-turn', true)
  }

  steer(input: UserMessage): void {
    this.send(input, 'next-step', true)
  }

  inject(input: UserMessage): void {
    this.send(input, 'next-step', false)
  }
```

### 注释

1. **`wakingAfterAbort`**：正在 abort 的 running/maintenance 上又 wakeup 时，不能把消息塞进「已死活动」的 `next-step`（可能永远没人 claim），**强制抬成 `next-turn`**。  
2. **`splice(..., Infinity, 0, [message])`**：追加到该桶末尾（并写成持久 `agent/inbox/spliced` 事件）。  
3. **`followup`**：新用户话 → `next-turn` + 唤醒。  
4. **`steer`**：中途插话 → `next-step` + 唤醒。  
5. **`inject`**：只入队、**不唤醒**（等下次 followup/steer，或正在跑的司机在 step 边界自己领）。

### 附：`cancel`（停）

```134:140:packages/core/agent-loop/src/agent.ts
  cancel(cause: AgentCancelCause, options: CancelOptions = {}): void {
    if (!options.keepInbox) {
      this.inbox.clear()
      if (this.phase.kind !== 'idle') this.phase.wakeRequested = false
    }
    if (this.phase.kind !== 'idle') this.phase.abort.abort(cause)
  }
```

**注释**：默认清空收件箱 + 清 latch + abort。`keepInbox=true` = 停当前模型轮，但保留已排队输入。

### 本节小结

| API | 桶 | 唤醒？ |
|-----|-----|--------|
| followup | next-turn | 是 |
| steer | next-step | 是 |
| inject | next-step | 否 |
| cancel | 可清队 | abort 当前活动 |

---

## 3. `wakeDriver`：什么时候真的开跑

**白话**：只有 `idle` 才会立刻 `kick`；若已经在忙，多数情况直接 return（活司机自己会领队），特殊情况只 latch。

### 代码

```172:193:packages/core/agent-loop/src/agent.ts
  private wakeDriver(wakeAfterAbort = false): void {
    if (this.phase.kind !== 'idle') {
      const reason = this.phase.abort.signal.reason as AgentCancelCause | undefined
      if (reason?.kind !== 'disposed' && (this.phase.kind === 'maintenance' || wakeAfterAbort)) {
        this.phase.wakeRequested = true
      }
      return
    }
    const driver = Promise.withResolvers<void>()
    this.activityDone = driver.promise
    this.setPhase({
      kind: 'running',
      abort: new AbortController(),
      turn: this.phase.lastTurn,
      step: 0,
      wakeRequested: false,
    })
    this.loopCtx.agents.withInitiator(this, () => this.kick()).then(driver.resolve, driver.reject)
  }
```

### 注释

| 情况 | 行为 |
|------|------|
| 已是 idle | 切 running → `withInitiator(kick)` |
| running 且未 abort | **什么都不做**（司机还活着，会自己 claim） |
| running 已 abort 且 `wakeAfterAbort` | 记 `wakeRequested`（除非 disposed） |
| maintenance | 同样可 latch |
| disposed | **绝不** latch（拆掉的 Agent 不该再开模型） |

`withInitiator`：后面工具调度里 `requireInitiator()` 靠这次绑定找到「是哪个 Agent」。

### 本节小结

唤醒不是「无脑开线程」：空闲才 kick；忙则要么靠现司机，要么 latch 等忙完。

---

## 4. `kick`：司机边界（错误吞在这里）

**白话**：一个 kick = 循环调用 `turn()`，直到没活或出错；**无论成败**最后回到 idle，若 latch 了再链式唤醒。

### 代码

```210:223:packages/core/agent-loop/src/agent.ts
  private async kick(): Promise<void> {
    try {
      while (await this.turn()) {}
    } catch (_error) {
      // Reported failures and cancellation are contained at the driver boundary.
    } finally {
      if (this.phase.kind === 'running') {
        const { turn, wakeRequested } = this.phase
        this.setPhase({ kind: 'idle', lastTurn: turn })
        if (wakeRequested && this.inbox.hasPending) this.wakeDriver()
      }
    }
  }
```

### 注释

- `turn() === true`：同一次 kick 里还有 pending → 再开一轮 Turn。  
- `turn() === false`：本 kick 结束。  
- **catch 空**：错误已在 `throwError` / 取消路径处理过，避免未处理 Promise rejection。  
- **finally**：回 idle；若 `wakeRequested` 且队列非空 → 立刻再 `wakeDriver()`。

### 本节小结

kick = **while(turn) + 保证回 idle + 可链式再醒**。外层不用担心「司机卡在 running」。

---

## 5. `preStep`：领消息 → 拼提示词 → 插件可拒绝

**白话**：每一步开始前固定四件事：claim、assemble、投影动态上下文、waterfall 决策。

### 代码

```225:243:packages/core/agent-loop/src/agent.ts
  private async preStep(target: InboxTarget, position: { turn: number; step: number }): Promise<PreparedStep> {
    if (this.phase.kind !== 'running') throw new Error(`agent "${this.id}": pre-step outside running phase`)
    const signal = this.phase.abort.signal
    const claimed = this.inbox.claim(target, position.turn)
    const assembly = await this.loopCtx.systemPrompt.assemble(assembleContextFor(this, signal))
    signal.throwIfAborted()
    const sections = renderContextSections(assembly)
    const context = this.runtimeContext.project(joinContextSections(sections), sections)
    const decision = await this.dispatch.waterfall(
      'agent/pre-step', { messages: claimed, ...position, signal },
      (): Promise<PreStepDecision> => Promise.resolve<PreStepDecision>({
        kind: 'enter',
        messages: context === undefined ? claimed : [...claimed, context],
      }),
    )
    signal.throwIfAborted()
    return decision.kind === 'reject' ? decision : { ...decision, assembly }
  }
```

### 注释（顺序不能乱想）

1. **`claim`**：从 Inbox 拿走消息并持久删除；就算后面 reject，**也不会自动塞回队列**。  
2. **`assemble`**：拼 system 段 + 工具 schema。  
3. **`runtimeContext.project`**：动态上下文相对上次有变才生成一条「未提交」的补充 user 消息。  
4. **默认 enter**：claimed ± 动态上下文。  
5. **waterfall `agent/pre-step`**：插件可改 messages，或 `reject`（压缩常挂这里）。  
6. **返回**：reject 原样；enter 时带上本次 `assembly`（每步可重新 assemble）。

### 本节小结

preStep = **领货 + 备料 + 安检**。安检不过 → 本 Turn 可能没有真正的模型 Step。

---

## 6. `turn`：开边界 → 多 Step → 关边界

**白话**：先写 `turn/start`，再循环 Step，最后无论成败写 `turn/end`。

### 6.1 打开

```246:261:packages/core/agent-loop/src/agent.ts
  private async turn(): Promise<boolean> {
    // ...
    const turn = phase.turn + 1
    try {
      this.session.append('turn/start', { turn })
    } catch (error: unknown) {
      this.throwError(error)
    }
    phase.turn = turn
    let turnEnds: TurnEndReason | null = null
    let target: InboxTarget = 'next-turn'
```

**注释**：先 append 成功再改 `phase.turn`；首步 target=`next-turn`（claim 会清掉 next-step 并取一条 next-turn）。

### 6.2 Step 循环（核心）

```263:301:packages/core/agent-loop/src/agent.ts
      while (true) {
        signal.throwIfAborted()
        const step = phase.step + 1
        const decision = await this.preStep(target, { turn, step })
        if (decision.kind === 'reject') {
          turnEnds = { kind: 'blocked' }
          return false
        }
        if (turnEnds && decision.messages.length === 0) break
        if (phase.step === 0 && decision.messages.length === 0) {
          turnEnds = { kind: 'completed' }
          return false
        }
        // ...
        this.session.append('step/start', { turn, step })
        phase.step = step
        try {
          for (const message of decision.messages) {
            this.session.append('user/message', message, { surfaceOp: 'append' })
          }
          const stepEnd = await this.step(decision.assembly)
          if (turnEnds === null || turnEnds.kind !== 'max-tokens') turnEnds = stepEnd
        } finally {
          this.session.append('step/end', { turn, step })
        }
        if (turnEnds && this.inbox.nextStep.length === 0) {
          await this.dispatch.serial('agent/turn-stopping', { turn, signal })
        }
        if (turnEnds && this.inbox.nextStep.length === 0) break
        target = 'next-step'
      }
```

### 注释（分支表）

| 条件 | 结果 | 人话 |
|------|------|------|
| reject | blocked，结束 kick | 有 Turn 边界，可能无 Step |
| 首步 messages 空 | completed | 叫醒了但没什么可喂给模型 |
| `step()` 返回 null | 继续 | 还有工具后续 Step |
| completed / max-tokens | 记结束原因 | max-tokens 粘性，不能被后面 completed 降级 |
| 将停且 next-step 空 | `turn-stopping` | 插件最后机会再塞一句 |
| 仍空 | break | 正常收轮 |
| 有 next-step | 继续，target=next-step | 外环/插入续跑 |

**注释**：`phase.step` 在 `step/start` **之后**才赋值；空首步判断用的是赋值前的 `=== 0`。

### 6.3 收尾

```302:329:packages/core/agent-loop/src/agent.ts
    } catch (error: unknown) {
      if (signal.aborted) {
        turnEnds = { kind: 'aborted', reason: signal.reason as AgentCancelCause }
        throw error
      }
      turnEnds = {
        kind: 'error',
        error: error instanceof LlmError
          ? error.failure
          : { message: errorChain(error), code: 'UNKNOWN' },
      }
      this.throwError(error)
    } finally {
      try {
        this.session.append('turn/end', { turn, reason: turnEnds! })
      } catch (error: unknown) {
        this.throwError(error)
      }
    }
    if (!this.inbox.hasPending) return false
    phase.abort = new AbortController()
    phase.wakeRequested = false
```

**注释**：abort → 标 aborted 再抛给 kick；其它错误 → 记 error + `throwError`；**finally 必写 `turn/end`**。若还有 pending → 换新 AbortController，`return true` 让 kick 再开一轮。

### 本节小结

Turn = **日志边界 + Step while + 必关闭**。工具还没跑完就 `step()` 返回 null，不会过早 `turn/end`。

---

## 7. `step`：调模型 →（可选）调工具

**白话**：一步 = 从日志投影 messages → 建请求 → 流式收答案 → 有 tool-call 就交给调度器（见附录 B）。

逻辑骨架（读源码时跟这个走）：

```text
deriveMessages()
  → buildRequest(...)
  → llm.stream → assistant/chunk* → assistant/message
  → 若有 tool-calls：executeToolCalls(...)
  → 若还要继续：return null（外层再开 step）
  → 否则：return completed | max-tokens
```

细节断点与 `buildRequest` 规则见下文第 8 节；工具并行见 [02](./02-tool-scheduler-runtime.md)。

### 本节小结

Step 是「一次模型回合」；有工具时一步会拆成「模型 → 工具 → 再模型」的多 Step。

---

## 8. `buildRequest`：请求怎么定型

**白话**：先提出 seed 配置 → `agent/request` 可改 → `prepareCall` → 条件写入 `request/header|context` → 冻结请求。

### 代码（结构）

```407:495:packages/core/agent-loop/src/agent.ts
  private async buildRequest(/* ... */): Promise<{ request: GenerateOptions; preparedCall?: PreparedLlmCall }> {
    const persistedHeader = session.requestHeader()
    // ... seedConfig from options or requestProposal(persistedHeader)
    const proposedConfig = await this.dispatch.waterfall(
      'agent/request', { turn, step, signal },
      () => Promise.resolve(seedConfig),
    )
    // prepareCall → canonicalHeader → request/header / request/context 条件 append
    const request = markAgentLoopRequest(deepFreeze({
      ...header.config,
      messages: boundaryMessages,
      ...header.system !== undefined ? { system: header.system } : {},
      ...header.tools !== undefined ? { tools: header.tools } : {},
      sessionId: this.session.id,
      signal,
    }))
    return { request, ...preparedCall === undefined ? {} : { preparedCall } }
  }
```

### 注释

1. **首次**：可用 `AgentOptions` 的 provider/model；effort 仅在同模型且非 adapterDefault 时恢复。  
2. **之后**：`requestProposal(persistedHeader)` 剥掉适配器默认值，让插件/prepareCall 重解析。  
3. **`agent/request`**：改路由、参数的挂点。  
4. **日志锚点**：第一次写 `request/header`；配置变了写 change；provider/model/窗口变了写 `request/context`。  
5. **`deepFreeze` + `markAgentLoopRequest`**：请求不可变，并标记来自 agent-loop。

### 本节小结

每次 Step 的 messages 都来自 **当下** `deriveMessages()`，不是内存里另藏一份数组。

---

## 9. 一次 `followup` 调用栈（带注释）

```text
followup(msg)
  │  // 用户新话
  ├─ send(next-turn, wakeup=true)
  │    ├─ Inbox.splice          // 持久写入 inbox/spliced
  │    └─ wakeDriver()          // 空闲则 kick
  └─ kick()
       └─ turn()
            ├─ turn/start
            ├─ preStep(next-turn)
            │    ├─ claim              // 领走队列
            │    ├─ assemble           // 系统提示词+工具
            │    ├─ runtimeContext     // 动态上下文
            │    └─ agent/pre-step     // 插件可拒
            ├─ step/start
            ├─ user/message × N        // 真正进表面历史
            ├─ step()
            │    ├─ buildRequest(deriveMessages())
            │    ├─ llm.stream → chunk* → assistant/message
            │    └─ executeToolCalls?  // → 附录 B
            ├─ step/end
            ├─ turn-stopping?          // 停前最后插话窗
            └─ turn/end
```

---

## 10. 调试速查

| 现象 | 先看 |
|------|------|
| 消息进队但模型不跑 | `wakeDriver`：是否 idle？是否 disposed？ |
| 有 turn 无 step | `preStep` reject 或首步空 messages |
| 工具跑了模型看不到 | `deriveMessages` / surfaceOp；或结果未按模型序 commit（附录 B） |
| 取消后又自己醒来 | `wakeRequested` 是否该清；dispose 是否误 latch |

---

## 本章总结

1. **入口三件套**：followup / steer / inject 只差「桶 + 是否唤醒」。  
2. **司机模型**：idle 才 kick；忙则靠现司机或 latch。  
3. **Turn/Step**：日志先开后关；一步 = 投影 → 模型 →（工具）→ 可能再一步。  
4. **真源**：一切给模型看的历史，必须能从 Session 事件投影出来。  
5. **扩展优先挂事件**：`pre-step` / `request` / `turn-stopping`，而不是改 `ReactLoopAgent` 私有方法。

下一篇：[02-tool-scheduler-runtime.md](./02-tool-scheduler-runtime.md)（工具并行与按序落盘）
