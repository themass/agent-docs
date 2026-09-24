# JobCome Prompt 与 Skill 设计

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 状态 | M1 冻结候选 |
| 关联 | [DeerFlow-Agent底座.md](DeerFlow-Agent底座.md) · [Agent聊天UI设计.md](Agent聊天UI设计.md) · [档案与简历编辑设计.md](档案与简历编辑设计.md) |

本文定义 **所有 Prompt 放哪、长什么样**——此前只有 Skill 清单，没有正文规格。

---

## 1. Prompt 分层总览

```text
┌─────────────────────────────────────────────────────────────┐
│ L0  Platform（DeerFlow harness 内置，不改源码）               │
│     工具调用规范、安全边界、read_file 等                        │
├─────────────────────────────────────────────────────────────┤
│ L1  JobCome 产品规则（注入 DeerFlow system 或 AGENTS.md）      │
│     访客/登录、Profile 真相源、禁止编造经历、MCP 必用           │
├─────────────────────────────────────────────────────────────┤
│ L2  Skill（SKILL.md，/skill-name 激活）                       │
│     resume-writer · coach-mock · …                            │
├─────────────────────────────────────────────────────────────┤
│ L3  Session 上下文（每轮动态）                                │
│     profile_id、job_id、locale、elevation_level、题库片段      │
├─────────────────────────────────────────────────────────────┤
│ L4  用户消息                                                  │
└─────────────────────────────────────────────────────────────┘
```

**非 Agent Prompt（不经 DeerFlow）：**

| 调用 | 模型别名 | Prompt 位置 |
|------|----------|-------------|
| 简历 MD→JSON | `jobcome-fast` | `prompts/ingest/profile_structurer.md` |
| JD 解析 | `jobcome-fast` | `prompts/ingest/jd_parser.md` |
| 扫描页 OCR 后结构化 | `jobcome-vision` | `prompts/ingest/profile_vision.md` |
| Reviewer 规则文案 | `jobcome-fast` | `prompts/export/reviewer.md` |

---

## 2. 目录结构（待实现）

```text
job-come/
├── prompts/                          # 非 Agent 单次调用 Jinja2
│   ├── ingest/
│   │   ├── profile_structurer.md
│   │   ├── profile_vision.md
│   │   └── jd_parser.md
│   └── export/
│       └── reviewer.md
├── skills/                           # DeerFlow Skill（多轮 Agent）
│   ├── public/
│   │   ├── resume-coach/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       └── elevation-rubric.md
│   │   ├── resume-writer/
│   │   ├── resume-reviewer/
│   │   ├── coach-mock/
│   │   ├── coach-archive/
│   │   └── coach-answer/
│   └── custom/
└── deploy/deerflow/
    └── product_rules.md              # L1 注入片段
```

代码通过 `PromptCatalog` 读取（禁止散落在 `service.py` 里硬编码长字符串）。

---

## 3. L1 产品规则（摘要）

```markdown
你是 JobCome 求职助手，帮助用户改简历与准备面试。

硬性规则：
1. 只能修改用户 Profile 中已有或用户当场确认的事实；不得编造公司、职位、年限。
2. 改档案必须调用 MCP jobcome_profile_patch，禁止只口头说「已改好」。
3. 拔高表述须可追溯；无法圆场的夸张必须标注 needsDefense。
4. 不讨论政治、不提供代投递、不生成歧视性内容。
5. 简历全文不要复述到聊天里；用字段 path 指代（如 experiences[0].highlights[1]）。
```

---

## 4. Skill 规格

### 4.1 `resume-coach`（简历 Agent 页默认）

**触发：** `/resume-coach` 或创建 `AgentSession.kind=resume`

**SKILL.md 要点：**

- 先 `jobcome_profile_get` 读当前 Profile
- 用户要改某段 → `profile_patch` + 说明改了什么
- 用户问「怎么拔高」→ 引用 `elevation-rubric.md`，建议档位，**不代替 Writer 生成全文**
- 可建议用户点「拔高预览」走 `POST /elevate`

### 4.2 `resume-writer`（拔高 / task 子 Agent）

**触发：** `POST /profiles/{id}/elevate` 或 task 子 Agent

**输出：** 必须符合 `ResumeDraft.sections` schema + `elevation_map`

**SKILL.md 要点：**

- 读 Profile + `elevation_level`（conservative | standard | elevated）
- 每句拔高写 `sourceText → writtenText`
- 一页中文简历：经历最多 4 段、每段最多 4 bullets

### 4.3 `resume-reviewer`

**触发：** 导出前 `ResumeService.export()`

**输出：** `{ "status": "passed"|"failed", "issues": [...] }`

**检查：** 假公司/假项目、无 Profile 证据的句子、联系方式不可选中等

### 4.4 `coach-mock` / `coach-archive` / `coach-answer`

见 [MVP-产品方案.md](MVP-产品方案.md) §4.4；Skill 正文待 W5 起逐份编写。

---

## 5. 非 Agent Prompt 示例：`profile_structurer.md`

```markdown
你是一个简历结构化助手。将输入的 Markdown 简历转为 JSON。

输出必须符合以下 JSON Schema（ProfilePayload）：
{{ schema_json }}

规则：
- 仅抽取原文明确出现的信息
- 不确定的字段 confidence 设为 needs_review
- 推测的设为 inferred，并在字段旁 notes 说明依据
- 日期统一 YYYY-MM
- 不要输出 markdown 代码块外的任何文字

简历 Markdown：
---
{{ resume_markdown }}
---
```

调用：

```python
prompt = catalog.render("ingest/profile_structurer", schema_json=..., resume_markdown=...)
response = await llm.chat(model=settings.job_come_llm_model_fast, messages=[...])
profile = ProfilePayload.model_validate_json(response.content)
```

**对象链：** `ModelResponse` → 取 `content` 字符串 → `ProfilePayload` 解析（不是裸 dict 传递）。

---

## 6. 视觉模型 Prompt：`profile_vision.md`

```markdown
你是简历 OCR 与结构化助手。输入为简历页面图片（可能为扫描件）。

任务：
1. 识别版面中的联系信息、经历、教育、技能
2. 输出 ProfilePayload JSON（同上 schema）
3. 看不清的字段 confidence=needs_review，不要猜

{{ schema_json }}
```

模型：`jobcome-vision` → 网关 `qwen-vl-ocr`（`YUAI_VISION_*` 独立配置）。

---

## 7. Session 上下文 Payload（L3）

创建 DeerFlow session 时 JobCome 注入 metadata + 首条 system 补充：

```json
{
  "profile_id": "prof_xxx",
  "profile_version": 3,
  "locale": "zh-CN",
  "elevation_level": "elevated",
  "job_id": null,
  "mode": "resume_coach"
}
```

DeerFlow thread 不存 Profile 全文；需要时 MCP `profile_get`。

---

## 8. Prompt 与可观测性

| 内容 | 进 Langfuse？ | 进 Context Usage 桶？ |
|------|---------------|----------------------|
| L0–L2 system | ✅（hash） | system_prompt / skills / tools |
| L3 session | ✅ metadata | conversation 或单独 bucket |
| 用户消息 | ❌ 全文（PII） | conversation |
| Profile 全文 | ❌ | —（仅 MCP 按需拉取） |

---

## 9. 实现状态

| 资产 | 状态 |
|------|------|
| Skill 目录结构 | ⏸ 文档已定，SKILL.md 未写 |
| `prompts/ingest/*` | ⏸ W1 |
| `PromptCatalog` | ⏸ W1 |
| DeerFlow session 注入 | ⏸ W2 |

---

## 10. 与模型的对应

| 逻辑别名 | Prompt 场景 |
|----------|-------------|
| `jobcome-fast` | structurer、jd_parser、reviewer |
| `jobcome-writer` | resume-writer Skill / elevate |
| `jobcome-coach` | coach-* Skills |
| `jobcome-vision` | profile_vision（OCR 页图） |

用户界面**永不展示**上述别名；仅 debug Context 面板可显示「本回合后端模型 hash」。
