# 术语表（先读这个）

> 白话解释 doc-sn 里会出现的名词。遇生词就回这里查。  
> **顶层封装边界（谁拥有什么）**先读 [00-顶层设计与实体边界.md](./00-顶层设计与实体边界.md)，不要只靠本表背词。

---

## 产品与入口

| 名词 | 白话意思 |
|------|----------|
| **PenguinHarness** | Prism-Shadow 的开源「Agent 构建平台」：用精简工具 + 文件型 Skill，让 Agent 能构建/优化 Agent。CLI `penguin`，Web 默认 `http://127.0.0.1:7364`。 |
| **`penguin`** | 命令行入口：`penguin web` / `chat` / `run` / `server` / `config`。 |
| **PENGUIN_HOME** | 数据根；默认 `~/.penguin/data`。开发可用 `~/.penguin/dev-data`。 |
| **Human 边界** | 不是一个接口类，就是 `session.run(...)` 这一进一出：输入 Prompt + 审批回调，输出 OmniMessage 流。CLI / Server / SDK 都是不同的 Human。 |

---

## 协议与循环

| 名词 | 白话意思 |
|------|----------|
| **OmniMessage** | 统一消息信封。流出去的、Trace 里存的、引擎内部传的，**同一种东西**。 |
| **ContextEngine / context_engine** | ReAct 编排内核：调 LLM → 审批 → 跑工具 → 再调 LLM，直到没有 tool_call。 |
| **Task** | 一次 `session.run`（无 Goal 时）：里面可有多轮 Request。 |
| **Request / Turn** | 一次对模型的调用（`runTurn`）。一轮可产生多个 tool_call。 |
| **MergeQueue** | 一轮里把「LLM 流 + 多个工具输出流」合成一条 yield 序列。 |
| **steer** | 运行中插话：塞进 `[user_steering]`，随下一 Request 输入送达；没有 Inbox。 |
| **carry-over** | 中断/失败后，把该补的输入带进下次 run。 |
| **stop_reason** | 终态六值：`completed \| failed \| aborted \| timeout \| malformed \| auth`。除 `auth` 外 LLM 失败会引擎内重连（有上限）。 |

---

## 三接口

| 名词 | 白话意思 |
|------|----------|
| **LLMInterface** | 模型侧：`streamGenerate`，只认 OmniMessage ↔ AgentHub。 |
| **EnvironmentInterface** | 工具侧：`executeTool` / `listTools`。 |
| **ApproveFn** | 每个 tool_call 一次「允不允许」的回调；由 CLI/Server 注入。 |
| **AgentHub** | `@prismshadow/agenthub`：真正的 Provider 协议适配；core 不直接绑厂商 SDK。 |
| **(provider, model_id)** | 模型身份恒为二元组，禁止拼接猜测。 |

---

## 状态与扩展

| 名词 | 白话意思 |
|------|----------|
| **Session** | 同一 Agent + Workspace 下的连续对话上下文；可多次 `run`。 |
| **Trace** | 追加式 JSONL；**恢复 Session 的唯一事实来源**。 |
| **Agent State** | `agent_state/`：`system_config.yaml`、`AGENTS.md`、skills、vault。 |
| **Project** | 项目层：`.project_config.toml`（模型表 + 凭据）。 |
| **Workspace** | Session 创建时定的工作目录（文件工具相对它操作）。 |
| **Skill / SKILL.md** | 文件型能力扩展；**不是插件运行时**。官方明确：Penguin 无 plugin 机制。 |
| **Vault** | 密钥文件（如 `.vault.toml`），权限宜 0600。 |
| **Goal / GOAL.yaml** | 多轮目标模式：每轮一个 Task，直到 complete/blocked 或预算用尽。 |
| **Subagent** | `run_subagent` 派生的子会话；默认深度上限 1。 |
| **Compaction** | 上下文压缩：`summarize` 或 `discard`；成功后可换新 LLM 对象并切 Trace 文件。 |
| **MCP** | 外挂工具服务器；首次 `listTools` 时连接。 |

---

## 六层运行模型

```text
Project → Agent → Workspace → Session → Task → Request
```

记不清时：上面管「装在哪、谁定义行为」，下面管「这一次怎么跑」。

---

## 一张对照：「用户发一句话」经过哪些词

```text
Human: session.run(prompt, { approve })
  → Session.ensureReady（首次：装工具 / MCP / LLM）
  → ContextEngine.run
       → runTurn: LLM.streamGenerate
       → 每个 tool_call → approve → Environment.executeTool
       → MergeQueue 合流 yield OmniMessage
       → 无 tool_call → Task 结束
  → 同时 Writer 追加 Trace
  → CLI/Web 渲染流
```

读正文时若再遇生词，先回本表。
