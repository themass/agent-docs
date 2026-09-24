# 项目工程标准（可复用）

| 项 | 内容 |
|---|---|
| 版本 | **1.0** |
| 日期 | 2026-09-03 |
| 状态 | **组织级冻结** |
| 适用范围 | 本 monorepo 内新建/维护的 **自研产品项目**（如 JobCome、NaviForge 等） |

本文是 **跨项目可复用** 的工程原则、架构分层、沉淀规范与默认技术选型。  
单个项目可在 `docs/工程规范.md` 中 **继承 + 覆盖** 本文，不得与之冲突。

**子文档：**

| 文档 | 内容 |
|------|------|
| [架构分层模板.md](架构分层模板.md) | 后端/前端目录、依赖规则、调用链 |
| [观测与Trace标准.md](观测与Trace标准.md) | trace_id、Langfuse、LiteLLM、日志 |
| [新项目启动清单.md](新项目启动清单.md) | 从 0 立项到 W0 的检查表 |
| [公共组件包.md](公共组件包.md) | **AgentKit** `libs/agentkit/` 边界与依赖方式 |

---

## 0. 公共组件包 AgentKit（P2 落地）

跨项目复用代码 **优先进入** [`libs/agentkit/`](../../libs/agentkit/)，产品通过 **path 依赖** 引用：

```toml
[tool.uv.sources]
agentkit = { path = "../libs/agentkit", editable = true }
```

含：`common`（trace/ids/logging）、`web`（FastAPI 基建）、`adapters/deerflow`、MCP 脚手架。  
产品仓库只保留 **业务 services / stores / 产品 MCP tools / skills**。

详见 [公共组件包.md](公共组件包.md)。

---

## 1. 总则（五条硬原则）

| # | 原则 | 含义 |
|---|------|------|
| **P1** | **边界清晰** | UI、API、业务、持久化、外部系统五层分离；跨层只传 `id` 或 DTO |
| **P2** | **沉淀复用** | 跨项目代码进 **`libs/agentkit/`**；产品内禁止长期双份 `common/` |
| **P3** | **适配器隔离** | 第三方 SDK / Agent 底座 / 云厂商 **只** 在 `adapters/`（或等价层）import |
| **P4** | **可观测默认可查** | 每个请求有 `trace_id`；LLM 走统一网关 + Langfuse；结构化日志 |
| **P5** | **最小可用交付** | 先打通一条用户路径再扩功能；文档与代码同步，不堆未实现架构 |

**不默认采用 DDD。** 默认：**Router → Service → Store / Adapter**，面向对象封装行为，模块按 **业务域** 切分。

---

## 2. 文档体系（每个项目必须具备）

```text
<project>/
├── AGENTS.md                 # AI/新人入口：路径、硬标准、文档索引
├── README.md                 # 一句话产品 + 文档链接
├── docs/
│   ├── 工程规范.md           # 继承本文 + 本项目覆盖项
│   ├── 技术方案.md           # 架构、选型、包结构
│   ├── MVP-产品方案.md       # 或等价产品规格（范围、页面、Schema）
│   └── …                     # 领域文档（鉴权、数据库、Agent 底座等）
├── .env.example              # 无密钥；真实配置不进 git
├── .python-version           # Python 项目：推荐 3.12
└── pyproject.toml / package.json
```

| 文档 | 谁写 | 何时冻结 |
|------|------|----------|
| 产品方案 | 产品/负责人 | 开工前 |
| 技术方案 | 技术负责人 | W0 前 |
| 工程规范 | 技术负责人 | W0 前（可引用本文） |
| 工程规范 **覆盖表** | 本项目 | 与本文冲突时显式列出 |

---

## 3. 技术栈默认值（可被项目覆盖）

| 层 | 默认选型 | 说明 |
|----|----------|------|
| 后端语言 | **Python 3.11+**（推荐 **3.12**） | `requires-python = ">=3.11,<3.13"` |
| API | **FastAPI** | 异步、OpenAPI 自生成 |
| 前端 | **Next.js App Router + TypeScript** | 业务 API 直连后端，MVP 不做 BFF |
| 关系库 | **MySQL 8** 或 PostgreSQL | 项目文档写明；表前缀 `xx_` |
| 缓存 | **Redis** | Session、限流、队列 |
| 对象存储 | **S3 兼容**（如阿里云 OSS） | 文件与 DB 分离 |
| LLM 网关 | **LiteLLM Proxy** | OpenAI 兼容单一入口 |
| LLM Trace | **Langfuse Cloud** | LiteLLM callback；不自建除非有合规要求 |
| 日志 | **structlog JSON** | 带 `trace_id`、`actor_id`、`event` |
| ORM | **SQLAlchemy 2.0** async | migration：Alembic |

覆盖示例：JobCome 用 MySQL + `jc_` 前缀 + DeerFlow → 写在 `job-come/docs/工程规范.md`。

---

## 4. 公共代码沉淀（P2 硬标准）

> **第二次出现的逻辑，必须进入公共包；禁止「先写 util 导出凑合」。**

### 4.1 后端（产品仓库）

产品内 **`{pkg}/common/` 仅作迁移缓冲**；稳定能力上提到 **AgentKit**。

| 目录 | 职责 |
|------|------|
| **`agentkit.*`**（依赖包） | trace、logging、web 基建、DeerFlow/OSS 适配器 |
| **`{pkg}/services/`** | 业务编排 |
| **`{pkg}/stores/`** | 持久化 |
| **`{pkg}/api/`** | HTTP 薄层 |
| **`{pkg}/agent/mcp/tools/`** | 产品 MCP 实现（调 services） |

### 4.1a AgentKit 模块（`libs/agentkit/`）

| 模块 | 内容 |
|------|------|
| `agentkit.common` | ids, trace, logging, crypto |
| `agentkit.web` | create_app, TraceMiddleware, Actor |
| `agentkit.adapters.deerflow` | DeerFlowSessionClient（唯一 import deerflow） |
| `agentkit.mcp` | McpToolRegistry |

### 4.2 后端（原 common 规则仍适用）

### 4.2 前端

| 目录 | 职责 |
|------|------|
| **`apps/web/lib/api/`** | 唯一 `fetch` 封装 |
| **`apps/web/lib/`** | auth、format、validators 等共享逻辑 |
| **`apps/web/components/`** | 纯 UI，不堆通用函数 |

### 4.3 判定表

| 场景 | 放哪里 |
|------|--------|
| 纯函数，≥2 模块用 | `common/` 或 `lib/` |
| 调云 API / Agent SDK | `adapters/` |
| 单域业务规则 | `services/` |
| 只用一次且不会复用 | 可暂留 Service，**不得**复制到第二处 |

### 4.4 Code Review 必问

1. 是否重复实现？应否沉淀？
2. 业务规则是否误放进 `common/`？
3. 第三方 import 是否越过了 `adapters/`？
4. Adapter 是否可注入、可 mock？

---

## 5. 架构分层（摘要）

完整模板见 [架构分层模板.md](架构分层模板.md)。

```text
Browser → apps/web（UI）
       → api/（HTTP + 鉴权 Actor）
       → services/（编排）
       → stores/（DB）  adapters/（OSS、LLM、Agent）
```

**依赖方向（硬）：** `api → services → stores | adapters`；`stores` 互不 import。

**Agent 类产品额外规则：**

- Agent **底座**（如 DeerFlow）= 黑盒，仅 `adapters/*_session_client.py` 可 import
- 业务真相在 **自有 DB**；Agent 只做对话态 + tool 循环
- 扩展：**Skill + MCP**，不改上游核心

---

## 6. 安全与配置

| 规则 | 要求 |
|------|------|
| 密钥 | 仅 `.env` / 密钥管理；**禁止**提交 git |
| 示例 | `.env.example` 占位，无真实密码 |
| 会话 | HttpOnly Cookie + 服务端 Session（Redis）；**不用** localStorage JWT |
| PII | trace / 日志 **默认不落** 正文（简历、手机号）；只记 id |
| 鉴权边界 | **API 为准**；前端 capabilities 仅 UX |

---

## 7. 观测（摘要）

完整标准见 [观测与Trace标准.md](观测与Trace标准.md)。

| 层 | 工具 |
|----|------|
| 请求关联 | `trace_id` + `X-Trace-Id` 响应头 |
| 业务日志 | structlog，`event` 命名 `{product}.{action}` |
| LLM | LiteLLM → **Langfuse**（metadata：`trace_id`, `user_id`, `skill`） |

---

## 8. Git 与交付

| 项 | 标准 |
|----|------|
| 提交 | 仅用户要求时 commit；信息写「为什么」 |
| 范围 | 最小 diff；不顺手改无关文件 |
| 测试 | 有意义的行为测试；不测显而易见断言 |
| CI（建议） | lint（ruff/eslint）+ 关键路径冒烟 |

---

## 9. 项目如何继承本文

每个项目在 `docs/工程规范.md` 顶部：

```markdown
## 继承

- 组织标准：[../../docs/standards/PROJECT_STANDARD.md](../../docs/standards/PROJECT_STANDARD.md)

## 本项目覆盖

| 项 | 组织默认 | 本项目 |
|----|----------|--------|
| 表前缀 | — | `jc_` |
| Agent 底座 | — | DeerFlow |
| … | | |
```

**仅写差异**；重复全文会造成漂移。

---

## 10. 当前采用本标准的项目

| 项目 | 工程规范 | AgentKit |
|------|----------|----------|
| JobCome | [job-come/docs/工程规范.md](../job-come/docs/工程规范.md) | path 依赖 `libs/agentkit` |

---

## 11. 修订

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-09-03 | 首版：P1–P5、沉淀、默认栈、Langfuse、分层 |

修订需说明：**影响哪些子项目**、是否需要同步更新各项目 `工程规范.md` 覆盖表。
