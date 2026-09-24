# Prime Agent — 核心运行时走查

> **配套**: [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) · [RUNTIME_AND_PERSISTENCE.md](./RUNTIME_AND_PERSISTENCE.md) · [ENTITY_AND_SEQUENCES](./ENTITY_AND_SEQUENCES.md)  
> **官方**: `prime-agent/packages/coding-agent/docs/quickstart.md`

本文用 **具体场景** 串起冷启动、第二问、attach、RLM、compaction。

---

## 场景 0：架构地图（读代码前）

| 你想找… | 文档锚点 | 源码 |
|---------|----------|------|
| 进程四层 | [PART1 §1.2.1](./ARCHITECTURE_PART1.md#121-进程分层总览client--daemon--worker--kernel) | `daemon-supervisor.ts`, `agent-session-runtime.ts` |
| 全栈类图 | [PART1 §1.2.2](./ARCHITECTURE_PART1.md#122-全栈实体全景客户端--daemon--worker--持久化) | 上表各路径 |
| 控制/数据面 | [PART1 §1.2.6](./ARCHITECTURE_PART1.md#126-控制面与数据面分离) | `daemon-protocol.ts`, `session-manager.ts` |
| Loop 四层 | [PART1 §7](./ARCHITECTURE_PART1.md#第7章runagentloop--agent-包核心循环四层深潜) | `agent-loop.ts` |

---

## 场景 1：首次 `prime-agent` 交互式启动

### 用户操作

```bash
cd ~/my-project
prime-agent
# TUI 出现，输入：Summarize the README
```

### 系统步骤

| 步 | 组件 | 动作 |
|----|------|------|
| 1 | `main.ts` | 解析 args；`ensureInteractiveDaemonRunning()` |
| 2 | Daemon | 若无 supervisor 则拉起；协商 protocol v7 |
| 3 | Worker | 为新 session 创建 `AgentSessionRuntime` + 空 jsonl |
| 4 | `AgentSession` | 启动 `KernelManager`（`~/.prime/agent/kernel-venv`） |
| 5 | TUI attach | `DaemonAgentConnection.attach` 收 snapshot |
| 6 | 用户 submit | `prompt` command → `_sessionInputPump` |
| 7 | `buildSessionContext` | 仅 system + user |
| 8 | `runAgentLoop` | `turn_start` → stream → 可能 IPython |
| 9 | `SessionManager` | 每条 message `append` 到 jsonl |
| 10 | TUI | 收 `message_end` / `turn_end` 渲染 |

### 首条 jsonl

见 [ENTITY §10.1](./ENTITY_AND_SEQUENCES.md#101-session-jsonl-头与-message-行)。

---

## 场景 2：同 Session 第二问（无 compact）

### 前置状态

jsonl 含：user₁, assistant₁（可能含 tool calls + tool results）

### 步骤差异

| 步 | 说明 |
|----|------|
| `buildSessionContext` | 加载全链 message entries |
| `agent.state.messages` | 设为重建数组 + 新 user₂ |
| `runAgentLoop` | Prompt 前缀 = 场景 1 结束时的 token 序列（modulo provider cache） |
| 持久化 | 追加 user₂、assistant₂ entries |

---

## 场景 3：Detach 后 `prime-agent attach`

### 用户操作

```bash
# 终端 A：prime-agent 跑着长任务，Ctrl+D detach
# 终端 B：
prime-agent attach <session-id>
```

### 关键点

- Worker **未**停止；kernel 变量仍在  
- Client 收 **generation + sequence** 重放后接 live  
- 若 worker 已死，supervisor 返回错误；`doctor --fix` 清理 lease  

时序：[ENTITY §8](./ENTITY_AND_SEQUENCES.md#8-端到端时序-cattach-断线重连)。

---

## 场景 4：模型调用 `rlm.run`

### IPython cell（模型生成）

```python
out = rlm.run("Scan all TODO comments and group by module", timeout=120_000)
print(out)
```

### 系统步骤

| 步 | 组件 | 动作 |
|----|------|------|
| 1 | Kernel | `host.request` type=`rlm.run` |
| 2 | `rlm-runtime.ts` | `createSubagent` → child `AgentSessionRuntime` |
| 3 | Child | 独立 `runAgentLoop`；可能独立 kernel |
| 4 | Child jsonl | 子 session 文件或子树 |
| 5 | Parent | 收结果；写 `child_usage_attributed` entry |
| 6 | Parent loop | tool result 回到父 messages |

`rlmDepth` 在 child header 为 parent+1。

---

## 场景 5：Auto-compaction 触发

### 触发条件（默认）

`calculateContextTokens(lastUsage) > contextWindow - reserveTokens`（见 `compaction.ts`）

### 步骤

| 步 | 动作 |
|----|------|
| 1 | Turn 结束，`shouldCompact` true |
| 2 | `compaction_start` 事件 |
| 3 | Summarization 模型生成 `summary` |
| 4 | `CompactionEntry` 写入 jsonl |
| 5 | `buildSessionContext` 截断旧 messages |
| 6 | `compaction_end`；可选继续 autonomous |

### 用户可见

上下文「跳跃」——旧细节只在 summary 与 artifacts 中；应用 `/tree` 或导出 jsonl 审计。

---

## 场景 6：RPC 无头一次 prompt

```bash
echo '{"command":"prompt","message":{"role":"user","content":"hello"}}' | prime-agent --mode rpc
```

路径：`runRpcMode` → `InProcessAgentConnection` 或 daemon（配置而定）→ 同 `AgentSession.prompt` → stdout 事件流。

与 TUI 差异：**无** TUI 渲染；事件 JSON 与 Daemon 内部形状经 RPC 适配层。

---

## 场景 7：`/goal` 跨 Turn

| Turn | 行为 |
|------|------|
| 1 | 用户 `/goal Fix all type errors` |
| 2 | `GoalState` 写入 custom entry |
| 3 | 每轮 assistant 后检查 goal 完成度 |
| 4 | Autonomous 可在预算内自动 follow-up 直至 goal cleared |

Goal 不改变 `runAgentLoop` 结构；在 `AgentSession` 层注入 system 片段与 continuation 策略。

---

### 调用链（带层级标注）

```text
L0 Client: main.ts → DaemonAgentConnection.prompt
L1 Daemon:  daemon-supervisor.ts → DaemonWorkerClient.forward
L2 Worker:  AgentSession.prompt → _sessionInputPump → _dispatchPreparedTurn
L3 Session: buildSessionContext() → agent.prompt
L4 Loop:    runAgentLoop → runLoop → streamSimple
L5 Tool:    ipython → KernelManager.executeCell
L1 Persist: AgentEvent → SessionManager.appendMessage → jsonl
```

---

## 场景 8：`buildSessionContext` 与 compaction 后第二问

### 前置

jsonl 含 `CompactionEntry`：`firstKeptEntryId = entry-040`

### 步骤

| 步 | 组件 | 动作 |
|----|------|------|
| 1 | `SessionManager` | 从 leaf 回溯 path |
| 2 | `buildSessionContext` | 发现 compaction → 注入 `CompactionSummaryMessage` |
| 3 | | 仅保留 entry-040 之后 message entries |
| 4 | `runAgentLoop` | 模型 prompt 前缀 = summary + 尾部（非全量历史） |

算法图：[PART3 §4.3](./ARCHITECTURE_PART3.md#43-buildsessioncontext-算法源码级)。

---

## 调试清单

| 现象 | 查 |
|------|-----|
| 无响应 | `prime-agent status`；worker 日志 |
| 上下文丢失 | jsonl compaction entries；`firstKeptEntryId` |
| RLM 失败 | `rlmDepth`；child session 文件 |
| 协议错误 | client/daemon 版本；capability 矩阵 |
| Kernel 死 | `doctor --fix`；重启 session |

---

返回 [文档中心](./README.md)
