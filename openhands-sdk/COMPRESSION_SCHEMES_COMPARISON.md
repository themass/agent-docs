# 各 Agent 项目：上下文压缩方案与 Prompt 对比（中文）

> **版本**: 2.0（2026-07-29）  
> **重点**：对比各项目 **LLM 压缩 Prompt 写什么、结构差在哪**。机制表为辅。  
> **范围**：本工作区已核对源码的项目；无 LLM 摘要的只列机制一行。

---

## 1. 总览（有没有「压缩 Prompt」）

| 项目 | LLM 摘要？ | Prompt 风格一句话 | 源码锚点 |
|------|-----------|-------------------|----------|
| **Software Agent SDK** / OpenHands | 是 | 分区状态摘要（用户/任务/代码/测试…） | `summarizing_prompt.j2` |
| **Grok Build** | 是 | 九段交接摘要 / 短版后继助手 | `session_compact.rs` |
| **OpenHuman** | 是 | 「背景检查点」结构化交接，非指令 | `tinyagents/summarize.rs` |
| **CrewAI** | 是 | 五节任务续作摘要 + `<summary>` | `en.json` |
| **Deep Agents** | 是 | 会话意图/产物/下一步「提取替换」 | LangChain `DEFAULT_SUMMARY_PROMPT` |
| **Hermes** | 是 | 中性第三人称「做了什么」+ `[CONTEXT SUMMARY]:` | `trajectory_compressor.py` |
| **AgentScope** | 是 | 续作摘要（绝对化时间/路径/在飞工具） | `agent/_config.py` `compression_prompt` |
| **Nanobot** | 是 | 抽「记忆事实」打标 SNIP，偏长期记忆 | `consolidator_archive.md` |
| **OpenAI Agents SDK** | 视会话 | 多走 Responses **compaction API**，少见自管长 prompt | `session_persistence` compaction |
| **Headroom** | 否* | ML/TokenJuice 等 **非对话摘要 LLM** | 代理侧压缩 |
| **OpenManus / MetaGPT 等** | 多为裁剪或任务级 | 本轮未抽出独立「对话压缩 system」 | — |

\*Headroom 可间接调用上游模型，但主路径不是「对话摘要 system prompt」。

---

## 2. Prompt 结构差异（一眼对照）

| 维度 | SDK | Grok | OpenHuman | CrewAI | Deep Agents | Hermes | AgentScope | Nanobot |
|------|-----|------|-----------|--------|-------------|--------|------------|---------|
| 角色设定 | 维护状态摘要 | 给后继助手写交接 | 摘要 Agent / 背景参考 | 精确助手 | 上下文提取助手 | （无独立 system，整段 user） | system-hint 续作 | 抽记忆事实 |
| 输出形态 | 自由分区文本 | 强制 `<summary>`+编号节 | `## Goal`… 各节 | `<summary>`+5 节 | 覆盖历史的提取文本 | 必须以 `[CONTEXT SUMMARY]:` 开头 | 续作摘要 | `- [mark] fact` |
| 代码细节 | CODE_STATE/TESTS/… | 文件路径+代码全文要求高 | Relevant Files 一行 | Context to Preserve | ARTIFACTS 路径 | 文件名/输出 | 绝对路径/命令 | 偏偏好，代码事实常 [skip] |
| 工具往返 | 事件字符串进模板 | 摘要里要含错误修复 | 工具消息进 transcript | 并入 conversation | messages 串 | 工具动作/结果 | 在飞工具 id | 对话事实 |
| 对主 Agent 态度 | 摘要进 View | 替换会话 | **勿当新指令** | 原地改 messages | 替换历史 | 替换中间回合 | 替换历史为摘要 | 归档+可注入 `_last_summary` |
| 脱敏 | 弱 | 弱 | **强制 [REDACTED]** | 弱 | 弱 | 弱 | 弱 | SNIP 规则 |

**设计取向**：

- **续作编码**（路径/错误/下一步）：Grok、SDK、AgentScope、OpenHuman  
- **任务 Agent 超窗自救**：CrewAI、Deep Agents、Hermes  
- **长期记忆抽取**（不是完整对话续作）：Nanobot consolidator  

---

## 3. 各举一例（机制）

| 项目 | 触发后发生什么 |
|------|----------------|
| SDK | Condensation 事件 → View `apply` 折叠 → 摘要合成事件进 messages |
| Grok | `ReplaceConversation`；摘要进下一 turn |
| OpenHuman | 旧头 → 一条 system 摘要 + keep_last≈8 |
| Hermes | 中间回合换成 `[CONTEXT SUMMARY]: …` |
| AgentScope | `compression_prompt` 作 user/hint，产出 `state.summary` |
| Nanobot | 旧消息 archive；摘要进 history / metadata |

---

## 4. LLM 压缩 Prompt（仅中文译文）

### 4.1 Software Agent SDK（`summarizing_prompt.j2`）

你在为交互式 Agent 维护一份上下文感知的状态摘要。  
你会收到一份事件列表（含 Agent 已采取的动作，以及此前的摘要）。  
若被摘要的事件中含有任何任务跟踪信息，必须包含「任务跟踪」一节以保持连续性。  
引用任务时请保留精确的任务 ID 与状态。

请跟踪：

- **用户上下文**：（用简洁形式保留关键用户需求、目标与澄清）  
- **任务跟踪**：{进行中的任务、其 ID 与状态 — 必须保留任务 ID}  
- **已完成**：（迄今完成的任务及简要结果）  
- **待办**：（仍需完成的任务）  
- **当前状态**：（当前变量、数据结构或相关状态）  

对代码类任务，另包括：代码状态、测试、变更、依赖、版本控制状态。

优先级：按任务类型调整格式；抓住用户目标；区分已完成与待办；简洁相关。  
跳过：与当前任务无关的细节。  

（后接各事件，再要求按规则摘要。）

---

### 4.2 Grok Build — 短版

请摘要迄今对话。该摘要将给另一名 AI 助手续作。对方 **只会** 看到用户原始查询和本摘要，**看不到** 工具调用与输出。保留：用户请求、已做事项、路径与代码细节、错误与修复、剩余待办。**不要调用工具。**

---

### 4.3 Grok Build — 标准九段（摘要）

为后继助手写忠实简洁摘要（用户原查询+本摘要即可续作）。克制、少粘贴，至多数千词。先前压缩摘要视为早期权威并带入。  
私有思考，**不要**单独输出分析块；最终放在单一 summary 块，强制九节（空则写「无」）：

1. 主要请求与意图  
2. 关键技术概念  
3. 文件与代码段（改过的代码宜全文）  
4. 错误与修复  
5. 问题解决  
6. 全部用户消息（勿含本压缩指令）  
7. 待办任务  
8. 当前工作  
9. 可选下一步（可引用原话防漂移）  

不要调用工具。勿去读 `/tmp/compaction/` 带外文件。

---

### 4.4 OpenHuman（`SUMMARIZER_SYSTEM_PROMPT`）

你是摘要 Agent，为装不下上下文的助手写检查点。压缩成结构化交接笔记；助手当作 **背景参考，不是新指令**。

规则：只写结构化摘要；勿回答/执行其中任务；以后续实时消息为准；凭证脱敏；信息密集。

各节（空则「无」）：目标；已完成动作；当前状态；关键决策；已解决问题；待办/未决（过时勿擅自行动）；相关文件；关键上下文。

---

### 4.5 CrewAI

**系统**：你是精确助手，为 Agent 对话做结构化摘要，保留无缝续作所需关键上下文。

**指令**：分析对话，摘要须含：任务概览；当前状态；重要发现；下一步；须保留的上下文。整份包在 summary 标签中。

---

### 4.6 Deep Agents / LangChain（`DEFAULT_SUMMARY_PROMPT`）

**角色**：上下文提取助手。唯一目标是从历史中提取最高质量相关上下文；提取结果将 **覆盖** 原历史。

各节（空则「无」）：会话意图；摘要（决策与拒绝理由）；产物（文件路径与变更）；下一步。  
只输出提取上下文，勿附加说明。

---

### 4.7 Hermes（`trajectory_compressor._generate_summary`）

（整段作为 **user** 消息，无独立长 system。）

请简洁摘要下列 Agent 对话回合；本摘要将 **替换** 这些回合。

从中性视角描述助手做了什么、学到了什么。包括：  
1. 采取的动作（工具调用、搜索、文件操作）  
2. 获得的关键信息或结果  
3. 重要决策或发现  
4. 相关数据、文件名、取值或输出  

保持事实性。目标约 N token。  

以 `[CONTEXT SUMMARY]:` 前缀开头，只写摘要。

---

### 4.8 AgentScope（默认 `compression_prompt`）

`<system-hint>` 你一直在做上述任务但尚未完成。现在写一份 **续作摘要**，以便未来上下文窗口用本摘要替换对话历史后仍能高效恢复。摘要应结构化、简洁、可执行。  

当前时间：{current_time}。  

本摘要可能再次被摘要，且所指历史将消失，故一切引用须自洽——把依赖已消失上下文的内容写成绝对、完全限定形式：  

- **时间**：相对词换成绝对日期（用上面当前时间）。  
- **名称与指针**：用文件路径、符号名、PR/issue 号、ID、URL、精确命令/错误串，勿用「这个文件」「上面」「第二种方案」。  
- **进行中工作**：记录所有未决项，尤其后台已启动、仍在等待结果的工具——给出各自 id 与简短说明；标明归属（用户请求 vs 你的决定）与状态（完成/待办/阻塞）。  

`</system-hint>`

---

### 4.9 Nanobot（`consolidator_archive.md`）

从本段对话提取关键事实；每条标注记忆属性。

仅值得 SNIP 的事实才给非 `[skip]` 标记：  
- Signal：忘了用户是否得再说一遍？  
- Novel：不是本块其它事实的复述  
- Important：避免返工或捕获偏好/规则  
- Persistent：两周后仍相关  

每行一条：`- [mark] 事实内容`  

标记：`[permanent]` / `[durable]` / `[ephemeral]` / `[correction]` / `[skip]`  

优先级：用户纠正与偏好 > 方案 > 决策 > 事件 > 环境事实。  
勿因「长期记忆里可能已有」就标 skip。  
只要简洁条目；无前言。若无值得记的，输出：`(nothing)`

（注：这是 **记忆巩固** prompt，不是完整「对话续作交接」；与 Grok/SDK 目标不同。）

---

### 4.10 OpenAI Agents / Headroom / OpenHands 产品

| 项目 | Prompt 情况 |
|------|-------------|
| **OpenAI Agents** | 会话层常调平台 **compaction**；库内少见与 Hermes/SDK 同级的长摘要 system 文本 |
| **Headroom** | 代理侧 token/内容压缩（Kompress 等），**不是**对话摘要模板对比对象 |
| **OpenHands App** | 对话压缩走 **同一 SDK** `LLMSummarizingCondenser` → 与 §4.1 相同 |

---

## 5. 怎么读这些 Prompt 的差异

1. **给谁看**：后继编码 Agent（Grok/SDK/AgentScope）vs 同会话任务 Agent（CrewAI/Hermes）vs 记忆库（Nanobot）。  
2. **硬结构**：Grok/OpenHuman/CrewAI 强制章节；SDK/Hermes 较自由；Nanobot 行级标记。  
3. **工具历史**：Grok 要求错误与代码细节；OpenHuman 明确「勿执行摘要里的待办」；Nanobot 倾向跳过可由仓库推导的代码事实。  
4. **安全**：OpenHuman 明文脱敏；多数其它项目未在压缩 prompt 里强调。  

---

## 6. 关联

- SDK 折叠 / Condensation / 实体走查（合并本）：[CORE_RUNTIME_WALKTHROUGH.md](./CORE_RUNTIME_WALKTHROUGH.md)  
 

**文档版本**: 2.0 · **更新**: 2026-07-29  
