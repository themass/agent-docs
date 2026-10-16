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

| 位置 | 责任 |
|---|---|
| `backend/server/src/jc/main.py` | FastAPI 应用、生命周期与 API 前缀 |
| `backend/server/src/jc/api/` | HTTP/SSE 路由、请求校验、认证与响应模型 |
| `backend/server/src/jc/services/` | 业务编排：档案、简历、JD、面试、会话、导出 |
| `backend/server/src/jc/stores/` | MySQL/Redis 资源访问与归属隔离 |
| `backend/server/src/jc/mcp/` | 受限 `jc_*` MCP 工具与权限检查 |
| `backend/server/src/jc/llm/` | 模型路由、调用与本地 LiteLLM 初始化 |
| `backend/server/src/jc/storage_*` | TOS/S3 与本地开发存储适配 |

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
