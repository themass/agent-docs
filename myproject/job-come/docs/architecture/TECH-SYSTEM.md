# TECH-ARCHITECTURE：系统架构与目录

- **状态**：已确认的 V1 实现架构
- **最后更新**：2026-10-15

## 1. 运行架构

```text
浏览器
  │ http://jc.sspacee.com
  ▼
Nginx
  ├── /              → Next.js（frontend/web）
  └── /api/v1/*      → FastAPI（backend/server）
                            ├── 内嵌 DeerFlow Agent
                            ├── MySQL
                            ├── Redis
                            ├── TOS / CDN
                            ├── LiteLLM / 模型提供方
                            └── Langfuse（可选 trace）
```

- 用户面向的主站是 `http://jc.sspacee.com`。
- 前端调用统一使用相对路径 `/api/v1`；Nginx 把它转发到 FastAPI，因此生产环境不需要浏览器跨域访问。
- **API 与内嵌 DeerFlow Agent 是一个 Python 进程**，不是两个独立服务；Next.js 前端是第二个进程。Nginx 是生产反向代理进程。
- V1 的数据库、缓存和对象存储为外部依赖；本地可在未配置 TOS 时使用本地对象目录兜底。

## 2. 目录契约

```text
frontend/
  web/                         # Next.js 应用、页面、组件、前端 API 客户端
backend/
  server/                      # FastAPI、数据库迁移、测试、服务端配置
    src/jc/                    # Python 包 jc
    alembic/                    # MySQL schema migration
    tests/                      # Python 测试
    nginx/                      # Nginx 配置样例
  agent/                       # Agent 不随业务代码散落
    deerflow/                  # DeerFlow config、扩展与产品规则
    skills/                    # 自研 SKILL.md
    prompts/                   # 非 Agent 的 LLM prompt
    llm/                        # 模型路由配置
    litellm/                    # LiteLLM 配置
  infra/
    hermes/                    # 基础设施集成资产
scripts/                        # setup、dev、验证、生产安装等入口
docs/                           # 仅保留当前规范与历史归档
```

不得重新引入根目录 `apps/web/`、`src/jc/`、`skills/`、`prompts/`、`deploy/` 等旧布局。

## 3. 服务端模块边界

依赖方向是**单向**的，且由 `backend/server/tests/test_architecture_layers.py` 强制执行。
完整契约与理由见 [`../decisions/ADR-004-layered-agent-architecture.md`](../decisions/ADR-004-layered-agent-architecture.md)。

| 位置 | 责任 | 不得依赖 |
|---|---|---|
| `src/jc/main.py` | FastAPI 应用、生命周期与 API 前缀 | — |
| `src/jc/api/` | HTTP/SSE 入站适配器：路由、校验、认证、响应模型 | — |
| `src/jc/mcp/` | Agent 工具入站适配器：`jc_*` 工具的参数解析与委派 | `api/`、`diagnostics/` |
| `src/jc/services/` | 业务编排（有状态、有 I/O）：档案、简历、JD、面试、会话、导出 | `mcp/`、`api/`、`diagnostics/` |
| `src/jc/agent/` | 角色定义、工具目录、消息成形 | `mcp/`、`api/`、`diagnostics/` |
| `src/jc/skills/` | 按角色组装 prompt（宿主侧组装，不靠模型读文件） | `services/`、`mcp/`、`api/`、`agent/` |
| `src/jc/llm/` | 模型路由、传输、failover、审计日志、多模态线格式 | `services/`、`mcp/`、`api/`、`agent/`、`adapters/` |
| `src/jc/stores/` | MySQL/Redis 资源访问与归属隔离 | 以上所有编排层 |
| `src/jc/domain/` | 纯方法论：岗位 playbook、结构规则、评分启发式。**零 I/O** | 一切有状态的层 |
| `src/jc/authz/` | `RunScope` 与归属守卫，失败即闭合 | 一切编排层 |
| `src/jc/diagnostics/` | 运维内省（harness 清单）。**读所有层，不被任何层依赖** | — |
| `src/jc/storage_*` | TOS/S3 与本地开发存储适配 | — |
| `src/jc/paths.py` | **仓库布局的唯一所有者**：根目录、prompt/agent 资产、配置路径解析 | 一切（它不 import 任何 `jc` 模块，故任何层都可用） |

两条最容易被破坏、也最该记住的规则：

- **入站适配器永远不是依赖。** `services/` 不能 import `mcp/`——工具调用只是一个调用方。
- **函数体内的 import 同样算依赖。** 分层测试用 AST 遍历全树，因为上一次的循环依赖正是靠函数内 import 藏住的。
- **不要再手算 `parents[...]`。** 走 `jc.paths`。这条曾经被 11 处代码用 4 种写法各自重算，其中一处少算一层，导致 `.env` 从未被加载、服务只能从 `backend/server` 目录启动。细节见 [`ADR-004`](../decisions/ADR-004-layered-agent-architecture.md) §1.1。

## 4. HTTP 与鉴权约定

- API 根路径固定：`/api/v1`（环境变量 `JC_API_PREFIX`）。
- 路由按资源分组：`/auth`、`/profiles`、`/jobs`、`/coach`、`/agent`、`/campaign`、`/notifications`、`/admin`。
- Web 与 API 使用同域 cookie；本地 HTTP 开发需 `JC_COOKIE_SECURE=false`，生产 HTTPS 时应开启 Secure cookie。
- 每一个档案、职位、会话、面试、导出物必须先验证当前用户归属，再读写资源。

## 5. 关键数据流

1. **建档**：文件上传 → 对象存储 → 文本/OCR 解析 → LLM 结构化 → profile draft → 用户确认。
2. **简历**：确认档案 → 优化/审稿 → HTML/PDF/DOCX 生成 → TOS → 有时效下载链接。
3. **JD**：用户粘贴或调用受限的公开页面读取 → 安全校验 → 结构化 → 匹配报告与来源元数据。
4. **Agent**：用户会话 → DeerFlow skill → 受限 `jc_*` 工具 → 业务服务/数据存储 → SSE 流式返回。

架构的安全细节见 [`TECH-AGENT.md`](TECH-AGENT.md)，依赖与命名见 [`TECH-DATA.md`](TECH-DATA.md)。
