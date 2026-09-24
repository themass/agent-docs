# JobCome Skill · Tool · MCP 集成清单

| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 用途 | **哪些必须有、哪些场景用、哪些不集成** |

---

## 0. LLM 路由（纠正：不用 proxy 也能 failover）

### 现状问题

- `deploy/litellm/config.example.yaml` 每个别名只绑 **一个** 后端，`simple-shuffle` 在同名多后端不存在时 **等于没有 failover**。
- 业务代码用 `httpx` 打 `OPENAI_API_BASE`，与你们 **SDK 直连 NewAPI** 的用法不一致。

### 目标架构（冻结）

```text
JobCome 业务 / DeerFlow
        │
        ▼
 jobcome.llm.router（litellm SDK，进程内）
        │  读 deploy/llm/routing.yaml
        │  scenario → [model_a, model_b, …] 顺序 failover
        ▼
 YuAI NewAPI（openai/mt-deepseek-v4-pro 等真实 slug）
```

- **不强制** `litellm --port 4000` 进程。
- **可选**：日后若要把 Langfuse 观测集中到网关，再启 proxy；业务仍走 `router` 抽象，不绑死。

配置模板：[`deploy/llm/routing.example.yaml`](../deploy/llm/routing.example.yaml)

| scenario | 用途 | failover 链（示例） |
|----------|------|---------------------|
| `ingest_fast` | 解析 MD→JSON、JD | deepseek → gpt-5-5 |
| `writer` | 拔高、改稿 | deepseek → gpt-5-5 |
| `coach` | 模拟面、点评 | gpt-5-5 → deepseek |
| `vision` | 扫描件 OCR | qwen-vl-ocr |
| `flash` | 短分类、轻量 | deepseek → gpt-5-5 |

---

## 1. 三层能力划分

| 层 | 是什么 | 谁调用 |
|----|--------|--------|
| **Prompt** | 单次 LLM（`prompts/*.md`） | `ProfileIngestService`、`ResumeReviewer` |
| **Skill** | 多轮 Agent 角色（`skills/*/SKILL.md`） | DeerFlow harness |
| **MCP Tool** | 读写业务数据 | DeerFlow → `jobcome.mcp.server` |

**原则：** 写 MySQL / TOS / 发邮件 **只走 MCP 或 JobCome Service**；Skill 里禁止假装「已改好档案」而不调 tool。

---

## 2. Skill 清单（DeerFlow）

### P0 — 没有就无法演示主流程

| Skill | 场景 | 状态 | 依赖 MCP |
|-------|------|------|----------|
| `resume-coach` | 简历页多轮对话、改稿建议 | ❌ 未写 | `profile_get`, `profile_patch` |
| `resume-writer` | 拔高生成 `ResumeDraft` | ⚠️ 规则在代码里，Skill 未挂 DeerFlow | `profile_get` |
| `resume-reviewer` | 导出前审稿 | ❌ 未写 | `profile_get` |

### P1 — 面试飞轮（阶段 3）

| Skill | 场景 | 状态 | 依赖 MCP |
|-------|------|------|----------|
| `coach-mock` | 模拟面试 | ❌ | `bank_search_questions`, `profile_get` |
| `coach-archive` | 真面后记真题 | ❌ | `interview_save` |
| `coach-answer` | 参考答法迭代 | ❌ | `answer_save_attempt`, `bank_search_questions` |

### P2 — 辅助

| Skill | 场景 | 状态 |
|-------|------|------|
| `resume-ingest` | Agent 内解析说明（可选） | ❌ |
| `jd-parser` | 粘贴 JD 后 Fit 分析 | ❌ |

### 不集成

| 来源 | 原因 |
|------|------|
| DeerFlow IM channels（飞书/Telegram） | JobCome 自有 Web + Cookie 鉴权 |
| 通用「写简历」GitHub Skill（无 MCP） | 无法写 Profile 真相源，会编造 |
| Auto_Jobs_Applier 类代投 Skill | 产品不做代投 |

---

## 3. MCP Tool 清单（JobCome 自研 `jobcome` server）

### P0 — 简历 Agent 页

| Tool | 作用 | 状态 |
|------|------|------|
| `jobcome_profile_get` | 读 Profile | ❌ `jobcome.mcp.server` 未实现 |
| `jobcome_profile_patch` | Agent 改字段 | ❌ |

### P1 — 面试辅导

| Tool | 作用 | 状态 |
|------|------|------|
| `jobcome_bank_search_questions` | 从个人库抽题 | ❌ |
| `jobcome_interview_save` | 记真题 | ❌ |
| `jobcome_answer_save_attempt` | 保存参考答法 | ❌ |

### P2 — JD / 战役

| Tool | 作用 | 状态 |
|------|------|------|
| `jobcome_job_parse` | JD 结构化 | ❌ |
| `jobcome_fit_score` | 人岗匹配 | ❌ |

注册配置：[`deploy/deerflow/extensions_config.example.json`](../deploy/deerflow/extensions_config.example.json)

### 外部 MCP — 默认不接入

| MCP | 结论 |
|-----|------|
| GitHub MCP | 与求职主流程无关 |
| 浏览器 / Playwright MCP | 不做代投、不爬招聘站（MVP） |
| 文件系统 MCP | DeerFlow 沙箱已有 `read_file`；业务文件走 TOS + API |
| 数据库 MCP | 必须经 JobCome tool 校验 `user_id`，禁止裸 SQL MCP |

---

## 4. 非 Agent Prompt（不经 DeerFlow）

| Prompt 文件 | scenario | 状态 |
|---------------|----------|------|
| `prompts/ingest/profile_structurer.md` | `ingest_fast` | ✅ 有文件，待接 `llm.router` |
| `prompts/ingest/profile_vision.md` | `vision` | ⚠️ 有文件，未接 |
| `prompts/ingest/jd_parser.md` | `ingest_fast` | ❌ |
| `prompts/export/reviewer.md` | `ingest_fast` | ❌ |

---

## 5. 可借鉴的 GitHub 项目（非 Skill 直引）

| 项目 | 借鉴什么 | 不做什么 |
|------|----------|----------|
| [deer-flow](https://github.com/bytedance/deer-flow) | harness、Skill、MCP 机制 | IM 通道 |
| [markitdown](https://github.com/microsoft/markitdown) | DOCX→文本 | 不替代 Profile JSON schema |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | PDF 抽文本 | — |
| [playwright-python](https://github.com/microsoft/playwright-python) | HTML→PDF | — |
| [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) | 漏斗思路（少而精） | 不抄代投 |
| agentskills.io 规范 | `SKILL.md` frontmatter 格式 | 不盲目装第三方 Skill |

**社区 Skill 仓库：** 仅当 Skill **显式依赖 `jobcome_*` MCP** 且通过审稿测试才可进 `skills/custom/`；默认 **零外部 Skill**。

---

## 6. 产品页 → 能力映射（一张表）

| 产品页 / 功能 | Prompt | Skill | MCP | API（已有） |
|---------------|--------|-------|-----|-------------|
| 上传解析 | `profile_structurer` | — | — | ✅ upload |
| 扫描件 | `profile_vision` | — | — | ⚠️ mock |
| 手改档案 | — | — | — | ✅ PATCH profile |
| 拔高预览 | — | `resume-writer`（应用内 builder） | — | ✅ elevate/preview |
| 导出 PDF/DOCX | `reviewer` | `resume-reviewer` | — | ✅ export |
| 简历 Agent 聊天 | — | `resume-coach` | profile_* | ❌ SSE |
| 模拟面试 | — | `coach-mock` | bank_* | ❌ |
| 记真题 | — | `coach-archive` | interview_save | ❌ |
| 忘记密码 / 验证邮箱 | — | — | — | ✅ 刚完成 |

---

## 7. 执行顺序（开发，不是让你测）

与用户要求对齐：**阶段 1–3 并行推进，先补主流程代码，再谈 E2E 验收。**

### 轨道 A — LLM + 解析（阶段 1）

1. 实现 `jobcome.llm.router` + `routing.yaml` failover
2. `ProfileStructurer` / vision 走 router，去掉 httpx 直连
3. Route C 扫描件接 `vision` scenario
4. `resume-writer` Skill 正文 + DeerFlow 单次 elevate 打通

### 轨道 B — 产品完整度（阶段 2）

5. `resume-reviewer` + 导出前检查
6. Profile 确认流 + 合并冲突 UI
7. `change-password`、邮箱验证 UX

### 轨道 C — Agent + 面试（阶段 3）

8. `jobcome.mcp.server`（P0 tools）
9. `skills/public/resume-coach` + Agent SSE 页
10. `coach-mock` / `coach-archive` + 面试辅导页
11. `DeerFlowSessionClient` 真接入（替换 stub）

---

## 8. 你需要提供的（阻塞项）

| 项 | 用途 |
|----|------|
| NewAPI 上各模型的 **准确 slug** | 写入 `routing.yaml` |
| Vision 模型是否就是 `qwen-vl-ocr` | `vision` 链 |
| DeerFlow `deerflow` pip 版本 / 是否已装 | 轨道 C |
| `JOB_COME_PUBLIC_URL` | 邮件链接（已说） |

**你不需要：** 再配 LiteLLM proxy、CDN 备案、企业邮箱（已有 QQ SMTP）。

---

## 9. 完整度总结（2026-09-03 更新）

### 自研 Skill — MVP **已齐**（7/7）

| Skill | 状态 |
|-------|------|
| resume-coach / writer / reviewer | ✅ |
| coach-mock / archive / answer | ✅ |
| jd-parser | ✅ |
| resume-ingest | ⏸ 可选 |

### 自研 MCP Tool — **已齐**（7/7）

| Tool | 状态 |
|------|------|
| profile_get / patch | ✅ |
| bank_search / interview_save / answer_save_attempt | ✅ |
| job_parse / fit_score | ✅ |

### 外部集成

见 **[开源集成指南.md](./开源集成指南.md)**：推荐 GitHub Skill/MCP、fork 规范、`extensions_config.example.json` 可选 MCP（默认关闭）。

### 仍可选增强（非阻塞）

- fork 社区 rubric 加深 `coach-mock` 评分维度
- 启用 markitdown / tavily / boss-agent MCP
- 前端 JD 粘贴页（API 已就绪：`POST /jobs/profiles/{id}/parse`）
