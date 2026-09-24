# JobCome Agent 核心能力：目标 · 现状 · 下一阶段

| 版本 | 1.0 |
| 日期 | 2026-09-04 |
| 范围 | 多轮 Agent（简历助手 / 面试教练 / 定向申请），不含单次 Prompt 管线 |

---

## 1. 目标（Agent 要成为什么）

产品层目标不变：**少而精、不代投、真相源在 Profile/Job/Interview**。

Agent 层目标拆成四条，缺一条都不算「核心能力齐」。

### G1. 能改真相源（可信）

- 改档案必须走 `jobcome_profile_get` → 用户确认 → `jobcome_profile_patch`
- 面试/答题/岗位必须走对应 MCP，禁止口头「已保存」
- 每次写库可追溯：session、skill、tool 名、参数摘要

### G2. 能跟一岗走完（可演示）

对一个 JD，用户只在聊天里说「帮我对这个岗」即可完成：

1. 读档案  
2. 解析/绑定 JD  
3. fit 打分并解释  
4. 定向改稿建议并落库  
5. 提醒走导出 / 或调用 apply-pipeline  
6. 针对该岗模拟面，记题、评分、保存 attempt  

这是 ai-job-search `/apply` + `/interview` 的 **Web Agent 等价物**。

### G3. 会话可靠（可回来接着聊）

- 刷新页面 / 重启 API 后，同一 `jc_agent_session` 能续聊
- 消息与 tool 轨迹落盘（或 Redis），不是进程内存
- 长对话可压缩，但 Skill 规则不丢

### G4. 体验像教练（不像聊天框）

- 真流式 token（不是整段一次性 dump）
- 可见 tool 调用（读档案 / 打分 / 保存）
- 写操作需确认（patch 前预览 diff）
- 简历页与岗位页共用同一套 session 协议

**非目标（明确不做）：** 真 DeerFlow 上游、代投、默认开外部 MCP、IM 通道。

---

## 2. 现状（对照目标）

### 2.1 已有（骨架）

| 层 | 现状 |
|----|------|
| Skill | `skills/public/` 7 个 + `skills/custom/apply-pipeline` |
| MCP | 7 个 `jobcome_*` handlers + stdio server |
| Runtime | `AgentRuntime`：system=SKILL.md，最多 6 轮 tool loop |
| API | `POST /agent/sessions` + SSE `.../messages` |
| 前端 | `AgentChatPanel`（简历页 / coach 页） |
| 绑定岗 | 创建会话可带 `job_id` → prep_pack 注入 system |

### 2.2 对照目标的缺口

| 目标 | 现状 | 严重度 |
|------|------|--------|
| **G1 工具真接到模型** | `stream_turn` 传 `tools=`，但 `LLMRouter.acompletion` **没有 `tools` 参数，也不会转给 litellm** | **P0 阻断** |
| G1 写库确认 | patch 无 diff、无前端确认 | P1 |
| G1 可追溯 | 有 `jc_agent_session` 行，**无消息/tool 日志表** | P1 |
| G2 一岗闭环 | 闭环在 **REST apply-pipeline**，Agent 不会编排该流水线 | P1 |
| G2 面试飞轮 | Skill 有，但 coach 不会强制 `bank_search` / `answer_save_attempt` | P1 |
| G3 续聊 | `_threads` **进程内存**；重启即 `Session not found` | **P0 体验** |
| G3 压缩 | 无 | P2 |
| G4 流式 | SSE 事件名叫 `token`，实际是 **整段回复一次推完** | P1 |
| G4 tool 可见 | SSE 有 `type=tool`，前端 **未展示** | P1 |
| Skill 加载 | 只读 `JOB_COME_SKILLS_DIR=skills/public`，**custom 技能加载不到** | P1 |
| DeerFlow | 文档规划了 LangGraph；代码是 **in-process 替代** | 可接受，非阻塞 |

### 2.3 一张能力图（现在 vs 目标）

```text
用户
  │
  ├─ 单次管线（已较强）
  │     上传解析 · fit · elevate · reviewer · export
  │
  └─ 多轮 Agent（骨架，核心未打穿）
        SKILL.md ──► 内存 messages
        MCP handlers 存在
        ⚠ 模型看不到 tools  →  不会调 MCP
        ⚠ 会话不落盘
        ⚠ UI 看不到 tool / 无确认
```

---

## 3. 下一阶段：Agent 核心能力（只做这 6 项）

排序原则：**先让 Agent 真的能调 tool 并续聊**，再谈体验与编排。

### P0-1 把 tools 接到 LLM（G1 的前提）

- `LLMRouter.acompletion(..., tools=, tool_choice=)` 透传 litellm
- 单测：mock litellm，断言 kwargs 含 tools
- 手工：简历 Agent「把电话改成 138…」必须出现 `jobcome_profile_patch`

**完成标准：** 日志里能看到 tool_calls；档案 version +1。

### P0-2 会话持久化（G3）

- 消息列表写入 Redis 或 `jc_agent_message`（JSON 即可）
- `stream_message` 按 `deerflow_thread_id` 加载，而不是只认内存 dict
- TTL 与 `JOB_COME_SESSION_TTL_DAYS` 对齐

**完成标准：** 重启 uvicorn 后同一 session_id 能续聊。

### P1-1 Skill 发现（public + custom）

- 加载路径：`skills/public/{name}` fallback `skills/custom/{name}`
- `apply-pipeline` 可被 `skill_hint` 选中

### P1-2 真流式 + tool 可见（G4）

- litellm `stream=True`，按 delta 推 `token`
- 前端：tool 气泡（读档案 / 打分 / 已保存）
- `profile_patch` 返回后刷新 ProfileEditor（或提示「档案已更新，请刷新」）

### P1-3 写操作确认（G1）

- 新增事件 `type=confirm`：patch 预览
- 或 tool 侧策略：patch 前必须 round-trip 用户「确认」
- MVP 可先：**前端展示即将写入的 JSON diff，点确认再发第二条消息触发 patch**

### P1-4 Agent 编排一岗（G2，接在 P0 之后）

不必再造一套流水线，让 Skill **调用已有 MCP/API 语义**：

1. `profile_get`
2. `job_parse` / `fit_score`
3. 建议改稿 → `profile_patch`（确认后）
4. 告知用户点「定向申请」或增加 MCP `jobcome_apply_pipeline`（薄封装现有 Service）

面试侧：coach-mock **每轮结束**调用 `answer_save_attempt`（无 question 则先写入题库再 attempt——若缺 tool 则补 `jobcome_question_upsert`）。

---

## 4. 明确不做（本阶段）

| 项 | 原因 |
|----|------|
| 接入真实 deer-flow LangGraph | 不阻塞 G1–G4；in-process 足够 |
| 外部 MCP（tavily/boss） | 主路径先自洽 |
| 多 Agent 子图（writer/reviewer 分进程） | 先单 skill tool loop 打穿 |
| 社区 Skill 大段 fork | 等 tool+会话可靠后再灌 rubric |

---

## 5. 建议执行顺序（约 1.5 周）

```text
Day 1–2   P0-1 tools 透传 + 最小集成测试
Day 2–3   P0-2 Redis 会话消息
Day 4     P1-1 custom skill 路径
Day 5–6   P1-2 流式 + 前端 tool 条
Day 7     P1-3 patch 确认（最小）
Day 8–9   P1-4 apply-pipeline MCP 薄封装 + coach 强制记 attempt
```

**验收口令（给内测用）：**

1. 「读一下我的档案」→ 出现 tool `profile_get`  
2. 「把姓名改成测试用户」→ 确认后 `profile_patch`，刷新编辑器可见  
3. 刷新页面，同一会话还能接着聊  
4. `/jobs` 进模拟面，答完一题后题库或 attempt 有记录  

---

## 6. 与产品路线的关系

- ROADMAP W4 内测 **依赖本阶段 P0**；否则 Agent 只是「会聊天的套壳」
- W5 灌 noamseg rubric **依赖 P0-1**，否则再好的 SKILL.md 也不会调 tool
- apply-pipeline REST 继续作为导出主路径；Agent 是编排入口，不是第二套导出引擎
