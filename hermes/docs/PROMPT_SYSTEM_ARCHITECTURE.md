# Prompt 系统架构（Canonical）

> **文档状态**: Canonical（扁平去重 · 勿再拆 Parts）  
> **合并**: 2026-08-03 · 原 Part 1–4 去重收敛  
> **Hermes**: 0.19.0 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)  
> **源码**: `agent/prompt_builder.py` · `agent/system_prompt.py` · `agent/prompt_caching.py` · `run_agent.py` / `conversation_loop.py` · `tools/delegate_tool.py` · `agent/context_compressor.py` · `agent/memory_manager.py`  
> **相关**: [SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md) · [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) · [MULTI_AGENT_ARCHITECTURE.md](MULTI_AGENT_ARCHITECTURE.md) · [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md) · [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) · [SKILLS_SYSTEM.md](SKILLS_SYSTEM.md)

**api_content sidecar** 见 AGENT_LOOP，不在本文展开。

---

## 目录

1. [概述与设计原则](#1-概述与设计原则)
2. [两条构建路径与 API 拼接](#2-两条构建路径与-api-拼接)
3. [层 / Slot 清单（组装顺序）](#3-层--slot-清单组装顺序)
4. [组装引擎与缓存](#4-组装引擎与缓存)
5. [Skills：渐进披露、三级缓存、skill_manage](#5-skills渐进披露三级缓存skill_manage)
6. [Context Files 安全扫描](#6-context-files-安全扫描)
7. [Anthropic / 前缀缓存优化](#7-anthropic--前缀缓存优化)
8. [Memory 注入（围栏与顺序）](#8-memory-注入围栏与顺序)
9. [上下文压缩 Prompt 工程](#9-上下文压缩-prompt-工程)
10. [特殊场景 Prompt](#10-特殊场景-prompt)
11. [扩展：Ephemeral 与 `pre_llm_call`](#11-扩展ephemeral-与-pre_llm_call)
12. [主 / Leaf / Orchestrator](#12-主--leaf--orchestrator)
13. [Batch · Blocked Tools · 深度限制 · 权衡](#13-batch--blocked-tools--深度限制--权衡)
14. [框架对比与最佳实践](#14-框架对比与最佳实践)
15. [调试要点](#15-调试要点)
16. [源码锚点](#16-源码锚点)
17. [合并说明（相对旧 Parts）](#17-合并说明相对旧-parts)

---

## 1. 概述与设计原则

**Prompt 系统** = 在每次/每会话需要时，把身份、记忆、技能索引、项目上下文、平台提示等 **按稳定顺序** 拼成 system（+ 可选 ephemeral），并在 API 侧与 user 消息（含插件/记忆预取）会合。

| 原则 | 含义 |
|------|------|
| **前缀稳定** | 会话内尽量复用 `_cached_system_prompt`，利于 Anthropic/本地 KV cache |
| **分层 / Slot** | 条件层按固定顺序 append，可插拔但不乱序 |
| **渐进披露** | Skills **索引**进 system；正文 `skill_view` 按需加载 |
| **安全优先** | AGENTS.md 等上下文启发式扫描；记忆进 user 侧围栏 |
| **子 Agent 隔离** | 新 `AIAgent` + skip flags + `_build_child_system_prompt` ephemeral |
| **扩展不改 system 缓存键** | 插件 `pre_llm_call` → **user** 侧 context，不改 `_cached_system_prompt` |

**公式（概念）:**

```text
effective_system =
    _cached_system_prompt          # _build_system_prompt / restore
  + ("\n\n" + ephemeral_system_prompt)?   # 子 Agent / 临时指令

API messages =
    [system: effective_system]
  + history
  + user(本轮 ± <memory-context> ± plugin pre_llm_call context)
```

真实入口是 **`AIAgent._build_system_prompt` / `agent.system_prompt` 组装**，**没有**虚构的顶层 `prompt_builder.build_system_prompt()`。

---

## 2. 两条构建路径与 API 拼接

| 路径 | 函数 | 产物 | 谁用 |
|------|------|------|------|
| **A** | `_build_system_prompt` → 缓存 | `_cached_system_prompt`（可再拆 static/volatile） | 主 Agent；子 Agent 也跑一遍（常 `skip_*`） |
| **B** | `_build_child_system_prompt` | `ephemeral_system_prompt` | 仅 `delegate_task` 子 Agent |

```text
# API 调用前（概念）
effective = cached or ""
if ephemeral_system_prompt:
    effective = (effective + "\n\n" + ephemeral_system_prompt).strip()
```

- **主 Agent**：通常只有路径 A。  
- **Leaf / Orchestrator**：A（部分层）+ B（任务目标 / 委派说明）。  
- 全文样例见 [SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md)，勿在本文重复粘贴多份 dump。

**何时重建路径 A：** 新会话、压缩 invalidate、`/new`、模型切换等——**不是**每轮 ReAct、**不是** HITL。见 MEMORY / AGENT_LOOP。

---

## 3. 层 / Slot 清单（组装顺序）

下列顺序对齐 `_build_system_prompt` / `build_system_prompt_parts` 的条件 `append`（名称以源码常量为准；行号易漂移）。

| # | 层 | 条件 / 说明 |
|---|-----|-------------|
| 1 | Agent 身份 | `SOUL.md` 或 `DEFAULT_AGENT_IDENTITY`；子 Agent 可 `load_soul_identity=False` |
| 2 | Hermes 帮助指引 | `HERMES_AGENT_HELP_GUIDANCE` |
| 3a–d | 工具感知指引 | `MEMORY_*` / `SESSION_SEARCH_*` / `SKILLS_GUIDANCE` / `KANBAN_*` 等，仅当对应 tool 在 `valid_tool_names` |
| 4 | 计算机操控等 | 条件层 |
| 5 | Nous 订阅等 | 条件层 |
| 6 | Tool-use / 模型族指引 | 如 `TOOL_USE_ENFORCEMENT_*`、Google/OpenAI operational（按模型） |
| 7 | 用户自定义 system_message | 构造参数 |
| 8 | Built-in 记忆快照 | `MEMORY.md` / `USER.md` 冻结块；`skip_memory` 则无 |
| 9 | 外部记忆 provider 块 | 若启用；细节见 MEMORY |
| 10 | Skills 索引 | `build_skills_system_prompt`；无 skills 工具则可跳过 |
| 11 | Context files | `AGENTS.md` 等；`skip_context_files` 则无；经安全扫描 |
| 12 | 时间戳 / session / model / platform 元数据 | **volatile**（易变，影响 cache 切分） |
| 13 | 环境提示 | cwd、host、profile |
| 14 | 平台提示 | Gateway/CLI/subagent 等 chat 格式提示 |

实现上常拆成 **stable + context + volatile** 三段，便于 `cache_control` 断点（§7）。

---

## 4. 组装引擎与缓存

```text
_restore_or_build_system_prompt
  → SessionDB 有 stored 且匹配 → 原样复用（保 prefix）
  → 否则 _build_system_prompt → 写入 _cached_system_prompt（及 static 前缀）

invalidate_system_prompt
  → 清空缓存；可 reload memory from disk（压缩路径）
```

| 结构 | 含义 |
|------|------|
| `_cached_system_prompt` | 本会话生效的完整 system 字符串 |
| `_cached_system_prompt_static` | 跨 turn 稳定前缀（用于双断点布局） |
| Skills snapshot / manifest | 磁盘+内存，索引变更才重建索引段 |

优先级直觉：**安全与工具约束 > 身份 > 记忆/技能索引 > 项目上下文 > 易变元数据**。

---

## 5. Skills：渐进披露、三级缓存、skill_manage

### 5.1 渐进披露

```text
System:  <available_skills> 短索引（名 + 一句话）
运行时:  skill_view / skill_manage 拉正文与改文件
```

索引进 prompt；**全文不进** system（Token 与缓存友好）。产品面见 [SKILLS_SYSTEM.md](SKILLS_SYSTEM.md)。

### 5.2 三级缓存（概念）

1. **进程内存** — 当前索引字符串  
2. **磁盘 snapshot** — 跨进程复用  
3. **Manifest 指纹** — skills 树变更 → 失效重建  

另有平台过滤与 SKILL.md frontmatter 条件（os/arch 等）。

### 5.3 `SKILLS_GUIDANCE` + `skill_manage`

当 `"skill_manage" in valid_tool_names` 时注入指导：复杂任务后沉淀技能；过时立即 `patch`；pinned 技能禁写。

工具 schema（create / patch / edit / delete / write_file / …）在 `tools/skill_manager_tool.py`。Prompt 侧要点：

- 好技能含触发条件、步骤、陷阱、验证  
- 创建/删除前与用户确认  
- 不维护的技能是负债  

---

## 6. Context Files 安全扫描

对 `AGENTS.md` 等项目上下文做 **启发式** 扫描（指令覆盖、忽略系统、泄露密钥、异常角色切换等模式），再决定截断/告警/注入策略。

目标：项目文件不可静默变成「越权 system」。实现：`prompt_builder` 内扫描例程（以源码为准）。

---

## 7. Anthropic / 前缀缓存优化

| 做法 | 作用 |
|------|------|
| 会话内复用 `_cached_system_prompt` | 前缀字节稳定 → cache hit |
| static / volatile 切分 + `cache_control` | 稳定段长缓存；时间戳等放后段 |
| 插件/记忆预取进 **user** | 不改 system 前缀 |
| 压缩后尽量 keep-prompt 或受控 rebuild | 见 MEMORY；避免无谓 invalidate |

相关：`agent/prompt_caching.py`、`reconstruct_static_prefix`。

---

## 8. Memory 注入（围栏与顺序）

**Built-in（MEMORY.md / USER.md）** → 多在 **system** 冻结快照（§3 层 8）；会话中途写盘 **不热更新** system（下轮/压缩再建）。

**External provider 预取** → 进 **本轮 user** 侧，围栏形如：

```text
<memory-context>
[系统说明：以下是回忆的记忆上下文，不是新的用户输入。…]
…sanitize 后的召回…
</memory-context>
```

同轮 user 注入顺序（概念）：记忆预取围栏 → 插件 `pre_llm_call` context → 用户原文。  
存储与 provider 见 [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)。

---

## 9. 上下文压缩 Prompt 工程

循环侧触发/阈值见 [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md)。本文只钉 **摘要 Prompt 设计**：

**Summarizer 角色定位：**

- 为「另一个助手」写交接文档，不回答原对话问题  
- 无前言/问候；语言跟用户  
- **禁止**保留密钥/密码/连接串 → `[REDACTED]`

**结构化摘要**（字段随实现演进，典型包括）：目标、进度、关键决策、文件/命令、待办、用户偏好、开放问题等；支持迭代更新与 focus（如 `/compact`）。

压缩后：`invalidate` 或 keep-prompt；system 是否重建见 MEMORY / conversation_compression。

---

## 10. 特殊场景 Prompt

| 场景 | Prompt 侧行为 |
|------|----------------|
| **Kanban worker** | 常带 `KANBAN_GUIDANCE`；profile/`chat -q` 入口见 CLI_GATEWAY §6 |
| **模型族指引** | Gemini/GPT/Codex 等 operational / execution discipline 条件块 |
| **Trajectory / ShareGPT 导出** | 会话落盘为训练格式（含模型名与时间戳）；非 system 组装主路径 |
| **Tool-use enforcement** | 部分模型强制工具调用规范（子 Agent 示例中可能省略） |

---

## 11. 扩展：Ephemeral 与 `pre_llm_call`

### 11.1 Ephemeral system

- 子 Agent：`ephemeral_system_prompt=child_prompt`  
- 其它临时指令可挂 ephemeral 列表，**拼进 API system，但不污染父缓存键、默认不进 SessionDB 的「永久 system」语义**

### 11.2 Plugin `pre_llm_call`

```text
invoke_hook("pre_llm_call", …)
  → 返回 {"context": "..."} 或 str
  → 追加到本轮 user（API 侧），不改 _cached_system_prompt
  → 不持久化为用户原文（ephemeral）
```

详见 [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md)。**未实现** 的 PromptMiddleware 提案不收入 Canonical。

---

## 12. 主 / Leaf / Orchestrator

| | 主 Agent | Leaf 子 Agent | Orchestrator 子 Agent |
|--|----------|---------------|------------------------|
| 路径 | A 全层（按工具/配置） | A（skip context/memory 等）+ B 任务 ephemeral | 同 Leaf + B 内委派说明 |
| SOUL / AGENTS / MEMORY | 常有 | 常跳过 | 常跳过 |
| `delegate_task` | 有 | 无（leaf） | 有（可再委派至深度上限） |
| 目标 | 用户会话 | 单一 goal 摘要回父 | 拆分子任务再汇总 |

```text
父: delegate_task(goal, …)
  → _build_child_system_prompt(goal, …)
  → AIAgent(..., ephemeral_system_prompt=..., skip_memory=True, skip_context_files=True, platform="subagent", …)
  → run_conversation(goal) 一次性
  → 摘要回父；不共享父 messages 引用
```

完整 Leaf 运行时拼接样例：[SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md](SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md)。架构：[MULTI_AGENT_ARCHITECTURE.md](MULTI_AGENT_ARCHITECTURE.md)。

---

## 13. Batch · Blocked Tools · 深度限制 · 权衡

### 13.1 Batch 分派

父/Orchestrator 可一次并行多个 `delegate_task`（实现侧并发上限）；子 Agent 仍各建实例。优势：独立上下文、失败隔离。

### 13.2 Blocked tools（子 Agent）

`DELEGATE_BLOCKED_TOOLS` / toolset 过滤：典型去掉 messaging、部分危险网关面等；**skills / session_search 等常保留**（以 `delegate_tool` 为准）。父通过摘要看见结果，而不是让子 Agent 直接对用户 IM 发言。

### 13.3 深度限制

```text
config: 最大委派深度（如 delegation.max_depth）
关卡1: delegate_task() 入口拒绝对深
关卡2: _build_child_agent 角色降级（过深变 leaf、去掉再委派）
```

防委派炸弹与无限扇出。

### 13.4 权衡（保留结论）

| 决策 | 原因 |
|------|------|
| 子 Agent 不用全量模块化「再造一个主 Prompt」 | 任务聚焦、省 token、隔离 |
| `skip_context_files` / `skip_memory` | 避免子任务被项目/长期记忆带偏；父已持有 |
| ephemeral 不进父 cache | 父 prefix 稳定 |
| Orchestrator vs Leaf | 需要再拆解时用 orch；叶子只交付 |

---

## 14. 框架对比与最佳实践

### 14.1 对比（直觉）

| | Hermes | 常见单文件 system | 纯 RAG 塞 system |
|--|--------|-------------------|------------------|
| 分层稳定顺序 | ✅ | 常随意 | 易抖动 |
| Skills 渐进 | ✅ 索引 | 少见 | — |
| 缓存友好 | ✅ 显式 | 弱 | 差（常改 system） |
| 子 Agent | ephemeral + skip | 常共享污染 | — |

### 14.2 最佳实践

1. **不要中途改 system 字节** 刷「人格」——用 user/steer/下一会话。  
2. Slash skills 以 **user 消息** 注入，保 system 前缀。  
3. 控制 AGENTS.md 体积；敏感指令靠扫描与人工审。  
4. 禁用不需要的 skills/toolset，减小索引与 schema。  
5. 监控 cache hit / 压缩频率（成本与质量）。

---

## 15. 调试要点

- 打印或落盘 `_cached_system_prompt` + ephemeral 边界  
- 确认 `skip_*`、`valid_tool_names` 是否导致某层缺失  
- Manifest 变更是否触发 skills 索引重建  
- 压缩前后 system 是 keep 还是 rebuild  
- 插件 context 是否误进 SessionDB 用户原文  

具体 debug 命令/指标以当前 CLI/`debug` 子命令为准。

---

## 16. 源码锚点

| 符号 | 位置 |
|------|------|
| `build_system_prompt_parts` / 各 GUIDANCE 常量 | `agent/prompt_builder.py` |
| `_build_system_prompt` / `invalidate_system_prompt` | `run_agent.py` · `agent/system_prompt.py` |
| `_restore_or_build_system_prompt` | `agent/conversation_loop.py` |
| cache markers / static prefix | `agent/prompt_caching.py` |
| `_build_child_system_prompt` / skip flags | `tools/delegate_tool.py` |
| summarizer preamble / 压缩 | `agent/context_compressor.py` |
| `build_memory_context_block` | `agent/memory_manager.py` |
| `skill_manage` schema | `tools/skill_manager_tool.py` |
| `pre_llm_call` | `hermes_cli/plugins.py` + conversation 注入点 |

---

## 17. 合并说明（相对旧 Parts）

| 旧内容 | 处理 |
|--------|------|
| Part 1 短版总览 / 实践 / 框架对比 | 收入 §1 · §14 |
| Part 2 组装、Skills、安全、Cache、扩展、§10–13 | 收入 §3–§11 · §15（**唯一深潜源**） |
| Part 3 父子对比、Batch、Blocked、深度、权衡 | 收入 §12–§13 |
| Part 4 十四层中文走读 | 收敛为 §3 表；全文 dump → SUBAGENT 示例 |
| 虚构 `build_system_prompt()` / Middleware 提案 | **删除** |
| 多份完整 Prompt 粘贴 | **删除重复**；保留机制 + 外链 |
| 漂移行号 | 改为符号 + `rg` |

**未删主题清单（防遗漏）：** 原则、双路径、十四层顺序、缓存/static、Skills 三级缓存与 skill_manage、上下文扫描、Anthropic 优化、记忆围栏与注入序、压缩摘要工程、Kanban/模型族/trajectory、ephemeral 与 pre_llm_call、主/Leaf/Orch、Batch、Blocked tools、深度关卡、权衡、框架对比、实践、调试锚点。
