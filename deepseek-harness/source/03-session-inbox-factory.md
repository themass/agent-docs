# 附录 C · Session / Inbox / 工厂源码走读

> 文件：`session/src/index.ts`、`agent/src/inbox.ts`、`agent-loop/src/index.ts`  
> 读法：每段 **白话 → 代码 → 注释 → 小节小结**；文末总总结。

### 本章你会搞懂什么

1. 一条事件怎么进日志、为什么 UI 和模型能对得上  
2. Inbox 为什么是「持久 spliced 事件的投影」，不是内存数组  
3. Agent 创建（prepare/publish/dispose）怎样避免半成品泄漏  

---

## 1. `Session.append`：写入边界

**白话**：往会话里追加一条事件。成功即提交；观察者挂了**不会**回滚日志。

### 代码（结构示意 + 真实约束）

```604:655:packages/core/session/src/index.ts
  append<T extends SessionEventType>(
    type: T,
    data: SessionEventMap[T],
    ...opts: T extends SurfaceEventType ? [opts: SurfaceIntent] : []
  ): SessionEvent<T> {
    // snapshotJsonValue(data) — 非 JSON 直接 throw
    // assertSupportedRequestHeader
    // 禁止 reentrant append（entry.appending）
    const event = deepFreeze({ type, seq: this.log.length, time: Date.now(), data, surface… })
    this.surfaceManager.validateNext(event)
    // push log → 清空 eventsSnapshot
    // invokeContainedSessionObservers('session/event') — 单 listener 失败不回滚 log
    return event
  }
```

### 注释

| 规则 | 人话 |
|------|------|
| `seq === log.length` | 序号连续从 0 涨 |
| 写入即提交 | persistence/UI 订 `session/event`；订户炸了日志仍在 |
| `deepFreeze` | 你事后改原对象，动不了已入日志的那份 |
| 禁止重入 | 同步监听器里再 `append` 同 session → 抛错 |
| Surface 类型要带 intent | 如 `user/message` 要 `surfaceOp`；`turn/start`、`assistant/chunk` 不要 |
| 热路径无 I/O | 落盘是别的插件异步缓冲 |

**resume / seed**：构造时 seed 也走 `validateNext`；`firstLiveSeq` 与 fork 谱系的 `seedLength` 不是一回事——调试恢复必读源码旁长注释。

### 本节小结

Session = **只追加的事实日志**。没有「改历史」；压缩用 replace 等 surface 操作表达「投影变了」。

---

## 2. `deriveMessages`：给模型看的投影

**白话**：不是扫全部事件，而是沿着 **surface.nodes（seq 列表）** 增量投影成 `messages[]`。

### 代码

```726:747:packages/core/session/src/index.ts
  deriveMessages(): Message[] {
    const surface = this.surface
    const nodes = surface.nodes
    const generation = surface.replaceGeneration
    if (generation !== this.derivedGeneration) {
      this.derived = []
      this.derivedNodes = 0
      this.derivedGeneration = generation
    }
    for (const seq of nodes.slice(this.derivedNodes)) {
      const msg = this.deriveEventMessage(this.log[seq]!)
      if (msg) this.derived.push(msg)
    }
    this.derivedNodes = nodes.length
    return [...this.derived]
  }
```

### 注释

1. **真源是 `nodes`**：chunk、纯 turn 边界常因无 surfaceOp 而不在 nodes。  
2. **`replaceGeneration` 变了**（压缩 replace）→ 整表重建。  
3. **增量**：只投影新 node，O(新节点)。  
4. **`deriveEventMessage` 返回 null**：例如空 content 的 assistant——事件仍在 log，但不进 transcript。  
5. **返回浅拷贝数组**：元素是冻结 Message；别改字段。

`agent.step` 每次调模型前都会 `deriveMessages()` → 与「日志为真」一致。

### 本节小结

模型上下文 = **surface 投影**，不是「内存里另维护的 messages」。UI 可以另订 chunk 做打字机效果。

---

## 3. Inbox：持久队列投影

**白话**：Inbox 看起来像两个数组（`next-turn` / `next-step`），真源是会话里的 `agent/inbox/spliced` 事件。崩溃恢复靠回放这些事件。

### 3.1 `splice` / `mutate`

**注释（读 `inbox.ts` 时对着用）**：

| 操作 | 人话 |
|------|------|
| `splice(target, start, deleteCount, items)` | 改某个桶；会 `append` 一条 spliced 记录 |
| `start=Infinity` | 归一成「追加到末尾」 |
| 回放 | 构造 Inbox 时从 session 事件重建两个桶 |
| `clear` | 清空投影并写持久删除语义 |

### 3.2 `claim`

**白话**：Turn/Step 开始时把该领的消息拿走，并从队列删除（再写 spliced）。

**注释**：

- `claim('next-turn')`：通常清空 next-step 侧策略 + 取一条 next-turn（以源码为准）。  
- `claim('next-step')`：领插入/续跑消息。  
- claim 后即使 `pre-step` reject，**消息也不会自动回队**（官方生命周期约定）。

### 本节小结

Inbox = **可恢复的投递队列**。不要自己再搞一个 `pendingMessages[]` 当第二真源。

---

## 4. AgentLoop 工厂：`prepare` / `publish` / `dispose`

**白话**：创建 Agent 像事务——准备期失败要清干净；对外可见之后，销毁路径要能 abort 并等静默。

### 注释（读 `agent-loop/src/index.ts`）

| 阶段 | 人话 |
|------|------|
| `prepare` | 建 Session/Agent 实例，尚未「对外宣布」 |
| `publish` | 写入 agents/sessions 注册表，别人找得到 |
| `dispose` | cancel（disposed）→ 等 idle → 撕注册 |
| 配置型 agents | 启动时 create/resume；失败发 contained 事件，不炸死整进程 |
| 身份 vs 路由 | sessionId 身份与 model 路由分开配置，避免 overlay 改模型丢掉身份键 |

**半成品**：prepare 失败必须走 dispose/清理，避免注册表里留幽灵 Agent。

### 本节小结

工厂保证：**要么完整可用，要么干净不存在**。

---

## 5. 三条路径如何咬合（带注释）

### 5.1 用户话 → 模型输入

```text
followup
  │  // 用户发送
  ├─ Inbox.mutate → append agent/inbox/spliced   // 持久入队
  ├─ wakeDriver → kick → turn
  ├─ preStep.claim
  │    ├─ 再写 spliced（删除已领）              // 队列投影更新
  │    └─ claimed 通知
  ├─ session.append('user/message', surfaceOp) // 进入表面历史
  └─ step → deriveMessages()                   // 投影进请求
```

### 5.2 助手流 → 可回放又可投影

```text
assistant/chunk × N     // 无 surfaceOp → 不在 nodes（打字机用）
assistant/message       // surfaceOp append，挂上 chunk 的 seq
deriveMessages → 一条 assistant Message
```

**注释**：回放完整过程看 log；喂模型看 surface。

### 5.3 工具结果 → 下一请求

```text
tool/call
tool/result (surfaceOp append, sourceEventSeqs=[callSeq])
deriveMessages 含 tool 结果
若还要继续 → 下一 step（可能 claim next-step 里的 additionalContexts）
```

### 本节小结

三条路径最终都汇合到：**append 事件 →（可选）进 surface → deriveMessages**。

---

## 6. 调试速查

| 问题 | 查 |
|------|-----|
| resume 后 inbox 空 | seed 切片是否跳过 spliced；是否 clear 过 |
| derive 缺消息 | 缺 `surfaceOp`？被 replace？空 assistant？ |
| append 报 reenter | `session/event` 同步回调里又 append |
| 创建失败泄漏 | prepare 失败是否 dispose |
| 双 agent 同 sessionId | 配置校验 / enter 冲突 |

---

## 7. 建议动手阅读顺序

1. `inbox.ts`（短）— 搞清 spliced 真源  
2. `agent.ts`：`send`→`wakeDriver`→`kick`→`turn`→`preStep`→`step`  
3. `tool-calls.ts`：`runGroup` / `commitReady`  
4. `tools`：`createExecution`→`prepare`→`dispatch`  
5. `session`：`append` + `deriveMessages`  
6. `agent-loop/index.ts`：`prepare` / `publish` / `dispose`  

官方时序：[docs/agent-lifecycle.zh.md](../../docs/agent-lifecycle.zh.md)

---

## 本章总结

1. **Session** 只追加；观察者失败不回滚。  
2. **deriveMessages** 是 surface 投影，不是第二份真源。  
3. **Inbox** 是 spliced 事件的可恢复投影；claim 不可轻易回滚。  
4. **工厂** 用 prepare/publish/dispose 保证不留半成品。  
5. 用户话、助手流、工具结果，都遵守同一条铁律：**模型可见 ⟺ 已记入可投影日志**。

返回：[source/README.md](./README.md) · 上一篇：[02](./02-tool-scheduler-runtime.md)
