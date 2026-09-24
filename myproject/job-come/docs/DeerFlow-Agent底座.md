# JobCome × DeerFlow Agent 底座

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 状态 | **Agent 底座冻结候选**（替代 Hermes） |
| DeerFlow 上游 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow)（`libs/agentkit/vendor/deer-flow/`） |
| 对照文档 | [OpenHarness Skill·MCP 对比](../../OpenHarness/docs/framework-comparison/20-skill-mcp-modules.md) · [08-mcp deer-flow 深潜](../../OpenHarness/docs/framework-comparison/08-mcp.md#4-deer-flow-langgraph-mcp-集成方案) |

---

## 1. 为什么选 DeerFlow（JobCome 视角）

| 需求 | DeerFlow 匹配 |
|------|----------------|
| C 端 Web + 多用户 | Gateway Run API + **Postgres checkpointer** 多副本（见 [17-deployment.md](../../OpenHarness/docs/framework-comparison/17-deployment.md)） |
| 简历 Writer / Reviewer / Coach 分工 | LangGraph + **子 Agent（`task`）** + Skill 按角色注入 |
| Skill 可维护 | 标准 **`SKILL.md`**，`public/` + `custom/` |
| 业务 Tool | **MCP 一等公民**（`extensions_config.json`） |
| 不改上游 | 只用 **`deerflow` harness 包** + 配置；**不用** IM `app/channels` |
| 业务真相在 JobCome | Profile / 面试库仍在 **PostgreSQL**；MCP 回调 JobCome |

**不采用的部分：** DeerFlow 飞书/Telegram Channel、`app/channels` 整套 IM——JobCome 自有 Next.js + FastAPI 账户体系。

---

## 2. 总体分工

```text
┌─────────────────────────────────────────────────────────────┐
│  JobCome（产品层，自研）                                      │
│  apps/web · jobcome/api · ProfileService · InterviewStore   │
│  账户 / 访客 / 导出 / SSE 对前端                             │
└───────────────────────────┬─────────────────────────────────┘
                            │ DeerFlowSessionClient
                            │ thread_id = f(user_id, coach_session_id)
┌───────────────────────────▼─────────────────────────────────┐
│  deerflow harness（黑盒，pip / monorepo 依赖 pin）            │
│  make_lead_agent → LangGraph · middleware · tool_search      │
│  skills/public + skills/custom · extensions_config MCP      │
└───────────────────────────┬─────────────────────────────────┘
                            │ stdio / http MCP
┌───────────────────────────▼─────────────────────────────────┐
│  jobcome-mcp-server（JobCome 实现）                           │
│  profile_get · profile_patch · bank_search · interview_save   │
└─────────────────────────────────────────────────────────────┘
```

**硬边界（与 DeerFlow 官方一致）：** `app → deerflow` 允许；JobCome 侧 **`jobcome` 不 import `deer-flow/app`**（不接 IM Gateway）。

---

## 3. Skill 体系（支持情况 + JobCome 用法）

### 3.1 DeerFlow 怎么支持 Skill

| 项 | 说明 |
|----|------|
| **标准** | `SKILL.md` + YAML frontmatter（与 agentskills.io / Cursor 同族） |
| **目录** | `skills/public/`（内置）· `skills/custom/`（安装/自研） |
| **沙箱路径** | 容器内 `/mnt/skills/` 映射宿主机 skills 目录 |
| **发现** | 启动/每 run 扫描；system prompt 注入 **`<skill_system>`** 索引（name + description + 路径） |
| **加载档位** | **L1 索引** → 模型 **`read_file`** 读全文（渐进披露） |
| **当轮激活** | 用户或路由 `/skill-name` → `SkillActivationMiddleware` **当轮注入 SKILL 全文** |
| **子 Agent** | `task` 子代理可把 **整份 SKILL.md 打进 system**（高 token，适合 Writer/Reviewer 专用子任务） |
| **安装** | Gateway `POST /api/skills/install` → 解压到 `custom/{name}/` |
| **压缩救援** | 对话压缩后通过 `skill_context` / 路径 **rescue**，避免重复读盘 |

参考：[`20-skill-mcp-modules.md` §3.3](../../OpenHarness/docs/framework-comparison/20-skill-mcp-modules.md#33-deer-flow)

### 3.2 JobCome 建议 Skill 清单

```text
job-come/skills/
├── public/                    # 随版本发布，映射 deer-flow skills/public
│   ├── resume-ingest/
│   │   └── SKILL.md           # 解析底稿、待确认字段规范
│   ├── resume-writer/
│   │   └── SKILL.md           # 拔高三档、sourceText→writtenText
│   ├── resume-reviewer/
│   │   └── SKILL.md           # 硬事实、拔高句圆场检查
│   ├── coach-mock/
│   │   └── SKILL.md           # 模拟面试、练手/目标语气
│   ├── coach-archive/
│   │   └── SKILL.md           # 记真题、入库字段
│   └── coach-answer/
│       └── SKILL.md           # 参考答法、挂 Profile 证据
└── custom/                    # 运营/用户扩展（可选，M2+）
```

| Skill | 触发场景 | 子 Agent 全文注入？ |
|-------|----------|---------------------|
| `resume-writer` | 拔高预览、导出前改稿 | 建议 **task 子 Agent** 专用 |
| `resume-reviewer` | Writer 之后审稿 | 建议子 Agent |
| `coach-mock` | 模拟面试页 | 主 Agent + `/coach-mock` 激活 |
| `coach-answer` | 参考答法迭代 | 主 Agent |

### 3.3 SKILL.md 引用文件约定

DeerFlow **没有** Hermes 的 `linked_files` 自动扫描；在 SKILL.md 里 **写明** 要读的引用：

```markdown
---
name: resume-writer
description: 按档位拔高简历表述，保留 sourceText 映射
---

Before writing, read `references/elevation-rubric.md` in this skill directory.
Use MCP tools `jobcome_profile_get` and `jobcome_profile_patch` for data.
```

关联脚本放 `skills/.../scripts/`，由模型经 sandbox `bash` 或 JobCome API 执行（**业务写操作只走 MCP**）。

---

## 4. MCP 体系（支持情况 + JobCome 用法）

### 4.1 DeerFlow 怎么支持 MCP

| 项 | 说明 |
|----|------|
| **配置** | 项目根 **`extensions_config.json`** → `mcpServers` |
| **客户端** | `langchain-mcp-adapters` · `MultiServerMCPClient` |
| **工具名** | 默认 **`{server}_{tool}`**（`tool_name_prefix: true`） |
| **传输** | **stdio** · **http** · **sse** |
| **热更新** | 改配置 **mtime** → `get_cached_mcp_tools()` 失效；或 `PUT /api/mcp/config` |
| **缓存重置** | `POST /api/mcp/cache/reset` |
| **OAuth** | `mcpInterceptors` 注入 token 刷新 |
| **大 schema** | `tool_search` + **DeferredToolFilter**（减绑模型上下文，不推迟执行） |
| **路由提示** | `routing.keywords` 软引导优先用某 MCP（如 jobcome 档案类） |
| **模块路径** | `deerflow/mcp/`（cache · client · tools · oauth） |

官方文档：`deer-flow/backend/docs/MCP_SERVER.md`

### 4.2 JobCome MCP Server 注册示例

见 [`deploy/deerflow/extensions_config.example.json`](../deploy/deerflow/extensions_config.example.json)。

```json
{
  "mcpServers": {
    "jobcome": {
      "enabled": true,
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "jobcome.mcp.server"],
      "env": {
        "JOB_COME_DATABASE_URL": "$JOB_COME_DATABASE_URL",
        "JOB_COME_MCP_SECRET": "$JOB_COME_MCP_SECRET"
      },
      "tool_name_prefix": true,
      "routing": {
        "mode": "prefer",
        "priority": 100,
        "keywords": ["简历", "档案", "profile", "面试", "题库", "bank"]
      }
    }
  }
}
```

暴露工具（JobCome 实现，名称经前缀后为 `jobcome_*`）：

| Tool | 作用 |
|------|------|
| `profile_get` | 读 Profile（`user_id` 来自 run metadata，不信模型参数） |
| `profile_patch` | Agent 建议改字段 |
| `bank_search_questions` | 个人面试库抽题 |
| `interview_save` | 记真题入库 |
| `answer_save_attempt` | 保存参考答法 / Attempt |

### 4.3 多租户与安全

```text
JobCome API 创建 Run 时写入 metadata:
  { "user_id", "profile_id", "guest_session_id?", "actor": "user|guest" }

MCP Server 进程:
  · 从 DeerFlow 注入的 session/run context 读 user_id
  · 禁止仅信任 tool 参数里的 user_id
  · 访客 run：仅开放 profile_get/patch；无 bank/coach 写（与 JobCome 能力矩阵一致）
```

---

## 5. 与 JobCome 产品页的映射

| 产品页 | DeerFlow 机制 | Skill | MCP |
|--------|---------------|-------|-----|
| 简历 Agent 多轮对话 | `thread_id` + SSE stream | `resume-writer` / `resume-reviewer` | `profile_*` |
| 访客拔高预览 | 单次 `runs/wait` 或短 thread | `resume-writer` 子 Agent | `profile_get` |
| 面试模拟 | 独立 `thread_id` per mock session | `coach-mock` | `bank_search` |
| 记真题 | Run 结束或 tool 回调 | `coach-archive` | `interview_save` |
| 参考答法 | 同题多 Attempt | `coach-answer` | `answer_save_attempt` |

---

## 6. 部署要点（C 端云主机）

| 组件 | 说明 |
|------|------|
| **jobcome-api** | 公网；鉴权、访客、创建 DeerFlow Run、代理 SSE |
| **deerflow worker** | 内网；`run_agent` + LangGraph（可与 api **同进程** MVP，后拆） |
| **PostgreSQL** | JobCome 业务表 + **LangGraph checkpointer** |
| **skills 卷** | 挂载 `job-come/skills` → DeerFlow `skills/` |
| **extensions_config.json** | 镜像构建或启动时渲染 |
| **不开 IM** | `config.yaml` 不启 channels |

---

## 7. 与 Hermes 方案差异（迁移备忘）

| 项 | Hermes（旧） | DeerFlow（新） |
|----|--------------|----------------|
| 运行时 | `hermes gateway` :8642 | `deerflow` harness / Run API |
| Skill 加载 | `skill_view` 三层 | system 索引 + `read_file` + `/skill` 激活 |
| MCP 配置 | `~/.hermes/config.yaml` | `extensions_config.json` |
| 会话 | Hermes SessionDB | LangGraph **thread_id** + Postgres checkpoint |
| 适配层类名 | `HermesSessionClient` | **`DeerFlowSessionClient`** |

业务层 **ProfileService / GuestMigration / 导出** 不变；只换 Agent 适配器与 skills/mcp 目录布局。

---

## 8. 开放项

| 项 | 建议 |
|----|------|
| 依赖方式 | MVP：`pip install deerflow` pin 版本；或 monorepo path 依赖 |
| 嵌入模式 | **同进程** `run_agent` vs 独立 Gateway 进程 |
| 记忆 | JobCome PG 为准；DeerFlow `memory.json` / OpenViking **仅辅助**，M2 再定 |
