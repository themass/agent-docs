# 附录 B · 工具调度器 + `ToolRuntime` 源码走读

> 文件：`tool-calls.ts`（调度）+ `tools/src/index.ts`（单次执行）  
> 读法：每段 **白话 → 代码 → 注释 → 小节小结**；文末总总结。

### 本章你会搞懂什么

1. 多个 tool-call 如何分组、并行  
2. 为什么 B 先跑完，日志里仍先出现 A 的结果  
3. 单次工具从审批到落盘经过哪些阶段  

---

## 0. 两层分别干什么？

**白话**：调度器管「一批调用怎么排」；Runtime 管「一次调用怎么安检、执行、收尾」。

| 层 | 入口 | 人话职责 |
|----|------|----------|
| Scheduler | `executeToolCalls` | 分组、并行池、**按模型顺序 commit**、abort 补假结果 |
| Runtime | `TOOL_RUNTIME_SCHEDULER` | prepare → guards → body → post → 通知 |

Step 只调 Scheduler；Scheduler 再调 Runtime 四阶段：

```text
prepare(exec)   → 准备好 / 直接终态
dispatch(exec)  → 真正跑工具（可并行重叠）
finalize(...)   → 跑 post-execute 再收尾
finish(...)     → 跳过 post 直接收尾
```

### 本节小结

改「顺序/并行」看调度器；改「审批/工具体」看 Runtime。

---

## 1. `executeToolCalls`：入口与分组

**白话**：把模型给出的 tool-call 列表变成一组组去跑；组首是 exclusive 就单跑，否则尽量整池并行。

### 代码

```59:101:packages/core/agent-loop/src/tool-calls.ts
export async function executeToolCalls(
  ctx: Context,
  turn: number,
  step: number,
  toolCalls: ToolCallBlock[],
  signal: AbortSignal,
  acceptContext: (context: UserMessage) => void,
): Promise<{ concluded: boolean }> {
  const agent = ctx.agents.requireInitiator()
  const { session } = agent

  const planned: PlannedCall[] = toolCalls.map(block => ({
    block,
    exec: {
      callId: block.id,
      name: block.name,
      arguments: parseArguments(block.arguments),
      agent,
      signal,
    },
  }))

  let next = 0
  let concluded = false
  while (next < planned.length) {
    const first = planned[next]!
    const mode = ctx.tools.executionMode(first.exec).kind
    const group = mode === 'parallel' ? planned.slice(next) : [first]
    const outcome = await runGroup(
      ctx, turn, step, group, mode, signal, acceptContext,
    )
    next += outcome.consumed
    concluded ||= outcome.concluded
    if (outcome.aborted) {
      for (const call of planned.slice(next)) appendSkippedToolCall(session, turn, step, call.block)
      return { concluded }
    }
  }
  return { concluded }
}
```

### 注释

1. **`requireInitiator()`**：必须在 `withInitiator(kick)` 里；否则找不到当前 Agent/Session。  
2. **`parseArguments`**：合法 JSON→对象；空→`{}`；非法→**保留原字符串**（让后面校验报错，调度器不吞）。  
3. **分组**：看组首 `executionMode`——`exclusive` 一组一个；`parallel` 先把剩余都扔进池（池内还可能再被打断，见下）。  
4. **abort**：本组中止后，对还没启动的调用写 synthetic skip，保证模型侧「每个 call 都有结果」。  
5. **`concluded`**：某个工具要求结束 Turn 时置位，向上回传。

### 本节小结

外层 while = **按组推进**；abort 也要给剩余 call 补结果，不能让 transcript 缺洞。

---

## 2. `runGroup` + `commitReady`：并行跑、顺序写

**白话**：这是整章最容易晕的地方——**执行可以乱序完成，写入 Session 必须按模型列出的顺序**。

### 2.1 思想图

```text
模型顺序:  A → B → C
实际完成:  B 先完，A 次之，C 最后

缓冲 slots: [空, B结果, 空]
commitReady: 卡在 A（下标0）→ B 先不落盘
A 完成:     [A结果, B结果, 空]
commitReady: 连续写下 A、B；C 仍等
```

### 2.2 关键行为注释（对着 `runGroup` 源码读）

读 `tool-calls.ts` 里 `runGroup` / `commitReady` 时，用这张表当注释：

| 机制 | 注释 |
|------|------|
| `maxParallelToolCalls` | 同时 in-flight 上限；来自配置，**下一组**才吃热更新 |
| `startCall` | 先 `append tool/call`，再 `prepare`（串行 await），再丢进 inFlight |
| `prepare` 串行 | 审批/pre-execute **有序**；只有 dispatch body 重叠 |
| Reclassify | 池里下一个若变成 exclusive → **停止填池**，留给外层当屏障组 |
| `commitReady` | 从左扫 slots，连续已完成的才 finalize + `append tool/result` |
| Abort | drain inFlight → commit 已启动的 → 未启动的 synthetic skip |
| Scheduler failure | dispatch 抛错记下来，在边界再抛；**不为未完成 call 造假**（与 abort 不同） |

### 2.3 落盘形状

```262:288:packages/core/agent-loop/src/tool-calls.ts
function appendToolCall(...) {
  return session.append('tool/call', { turn, step, callId, name, arguments }).seq
}
function appendToolResult(..., callSeq) {
  session.append('tool/result', {
    turn, step, message, error?, meta?,
  }, { surfaceOp: 'append', sourceEventSeqs: [callSeq] })
}
```

**注释**：

- `tool/call` 先写，拿到 `callSeq`。  
- `tool/result` 带 `sourceEventSeqs: [callSeq]`，回放/UI 能把结果绑回调用。  
- `meta`：展示用（diff 等），一般不进模型 content。

### 本节小结

**并行 = 跑得快；commitReady = 历史不乱。** 调试「顺序乱了」优先打断点在 `commitReady`。

---

## 3. `ToolRuntime`：一次调用的流水线

### 3.1 调度器怎么挂上 Runtime

```796:801:packages/core/tools/src/index.ts
  readonly [TOOL_RUNTIME_SCHEDULER]: ToolRuntimeScheduler = {
    prepare: exec => this.prepareScheduledExecution(exec),
    dispatch: exec => this.dispatchScheduledExecution(exec),
    finalize: (exec, result) => this.finalizeScheduledExecution(exec, result),
    finish: (exec, result) => this.finishScheduledExecution(exec, result),
  }
```

**注释**：Symbol 键，故意不进普通公开目录；主要给 agent-loop 用。

### 本节小结

Scheduler 不自己跑工具体，只编排这四个函数。

---

### 3.2 `createExecution`：Code Mode 折叠（安全）

**白话**：Code Mode 下，模型「表面上」能看见很多工具，但**只允许直接调** `run_code`；其它直接调用在进审批前就被否掉。

### 代码（结构）

```1364:1450:packages/core/tools/src/index.ts
  private createExecution(exec: ToolExecutionInput): ScheduledToolPreparation | { kind: 'ready'; exec: MutableToolRunContext } {
    // ...
    const visible = this.get(name, agent)
    const collapsed = visible !== undefined && this.collapses(name, agent, parent !== undefined)
    // ...
    if (collapsed) {
      if (signal.aborted) {
        return { kind: 'final-result', exec: execution, result: toolAbortedBeforeDispatchResult() }
      }
      return {
        kind: 'final-result',
        exec: execution,
        result: toolErrorResult(new ToolNotFoundError(
          name,
          `only \`${RUN_CODE_NAME}\` is callable directly — ...`,
        )),
      }
    }
    return { kind: 'ready', exec: execution }
  }
```

```1324:1326:packages/core/tools/src/index.ts
  private collapses(name: string, scope: ScopeKey | undefined, nested: boolean): boolean {
    return !nested && this.modeFor(scope) === 'code' && name !== RUN_CODE_NAME
  }
```

### 注释

1. **collapsed 且可见** → 在策略流水线**之前** final-deny（监听器/审批**不能**批准一个注定失败的直接调用）。  
2. **错误文案**引导去 `run_code`，避免模型以为「列表有工具却 unknown」。  
3. **`parent !== undefined`（嵌套）** → 不 collapse（代码里间接调其它工具合法）。  
4. **`modeFor(scope)`** 走作用域链，不是只看全局 defaultMode。

### 本节小结

Code Mode 的安全闸在 `createExecution`，不在 UI，也不在审批对话框。

---

### 3.3 `prepareExecution`：pre → ask → guards

**白话**：创建成功后，过瀑布 `tools/pre-execute`，可能变成 ask（问人），再过 guards；出口分三种。

### 代码（结构）

```1463:1506:packages/core/tools/src/index.ts
  private async prepareExecution<T>(input, next): Promise<T> {
    const created = this.createExecution(input)
    if (created.kind !== 'ready') return next(created)
    const exec = created.exec
    if (this.callerCancelled(exec)) {
      return next({ kind: 'final-result', exec, result: toolAbortedBeforeDispatchResult() })
    }
    try {
      const gate = await this.ctx.waterfall(
        carrier, 'tools/pre-execute', exec,
        () => Promise.resolve<PreToolDecision>({ kind: 'allow' }),
      )
      const askResolution = gate.kind === 'ask'
        ? await this.serviceAsk(exec, gate)
        : { decision: gate, approvalCancelled: false }
      // ... deny → post-result；allow → dispatch
      return await next({ kind: 'dispatch', exec })
    } catch (error: unknown) {
      return next({ kind: 'final-result', exec, result: toolErrorResult(error) })
    }
  }
```

### 注释（出口）

| kind | 何时 | 后续 |
|------|------|------|
| `final-result` | collapse / 早 cancel / pre 抛错 | `finish`（**不**跑 post） |
| `post-result` | deny / ask 中取消 | `finalize`（**跑** post，方便审计） |
| `dispatch` | allow 且过 guards | 去执行 body |

**注释**：拒绝也常走 post-result——post-execute 仍能看见「被拒绝了」。

### 本节小结

审批/拒绝挂在 prepare；真正 `tool.execute` 还没开始。

---

### 3.4 `dispatch`：跑 body

**白话**：`tools/execute` waterfall 默认落到 `dispatchToolBody`：合并 abort 信号，调 `tool.execute`，处理中途取消。

### 注释要点

1. `fuseToolSignals`：around 中间件可换 signal，但 **caller abort 仍并入**。  
2. 已 abort → 直接 `ABORTED_BEFORE_DISPATCH`，不调 body。  
3. body 抛错 → `toolErrorResult`（仍可能进 post）。  
4. `deferContext` / `concludeTurn`：工具可要求「额外塞上下文」或「结束 Turn」；调度器在 commit 时读取。

### 本节小结

dispatch = 唯一真正碰副作用（写文件/跑 shell）的阶段（在 allow 之后）。

---

### 3.5 `finalize` / `finish` / 通知

```1631:1645:packages/core/tools/src/index.ts
  private finishScheduledExecution(exec, result): ToolExecutionResult {
    materializedResult = materializeFinalResult(result)
    finalResult = materializeFinalResult(applyFinalContent(exec, materializedResult))
    this.notifyResult(exec, finalResult)
    return finalResult
  }
```

**注释**：

- `finalize` = post-execute waterfall + finish。  
- `notifyResult`：冻结 exec 后 `emit('tools/result')`；观察者挂了只 warn，**不改**返回值。  
- 权威结果以**返回值**为准；emit 是只读广播。

### 本节小结

落盘由调度器 `append tool/result`；Runtime 负责算出「结果对象」并通知。

---

## 4. 端到端小故事：两个 parallel 工具

```text
模型一次给出 [A, B]，都是 concurrencySafe

executeToolCalls
  └─ runGroup(parallel, [A,B])
       startCall(A): tool/call A → prepare A → dispatch A（飞）
       commitReady: A 未完 → 不写 result
       startCall(B): tool/call B → prepare B → dispatch B（飞）
       B 先完 → 填 slots[1]，commitReady 仍卡在 A → B 先不落盘
       A 完 → 填 slots[0]
       commitReady: 写 tool/result A，再写 tool/result B
```

**注释**：若 A 是 exclusive，则先整组跑完 A（含 result），再开 B 那一组。

---

## 5. 调试速查

| 现象 | 先看 |
|------|------|
| 结果顺序乱 | `commitReady`；是否绕过 scheduler 直接 `tools.execute` |
| 批准了不该直接调的工具 | `createExecution` collapse；`modeFor(scope)` |
| 取消后缺 tool/result | `appendSkippedToolCall` / `ABORTED_BEFORE_DISPATCH` |
| 拒绝听不到 post | 拒绝应是 `post-result` 不是 `final-result` |

---

## 本章总结

1. **两层**：Scheduler 管批与顺序；Runtime 管单次安检与执行。  
2. **铁律**：并行执行可以乱序完成，**Session 提交必须跟模型序**。  
3. **Code Mode**：折叠发生在 createExecution，审批救不了直接乱调。  
4. **拒绝也常走 post**：方便审计/遥测。  
5. **每个 call 最终都要有结果形态**（含 abort skip），否则下一轮模型上下文缺洞。

上一篇：[01](./01-react-loop-agent.md) · 下一篇：[03](./03-session-inbox-factory.md)
