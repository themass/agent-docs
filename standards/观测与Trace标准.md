# 观测与 Trace 标准（可复用）

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 父文档 | [PROJECT_STANDARD.md](PROJECT_STANDARD.md) |

---

## 1. 三层观测（所有项目统一）

| 层 | 内容 | 工具 |
|----|------|------|
| **L1 请求** | HTTP、DB、Redis、OSS、SSE 耗时 | `trace_id` + structlog；M2+ OTel |
| **L2 LLM** | model、tokens、cost、latency | **LiteLLM** → **Langfuse** |
| **L3 审计** | 登录、导出、删数据等产品事件 | 日志 `event`；可选 `{xx}_event` 表 |

**不要混成一套：** LLM 明细给 Langfuse；业务审计不给 Langfuse 塞全文。

---

## 2. 关联 ID（冻结）

| ID | 生成 | 传播 |
|----|------|------|
| `trace_id` | API 入口 | 日志、响应头 `X-Trace-Id`、Agent metadata、LiteLLM metadata |
| `actor_id` | 鉴权 | `usr_*` / `gst_*` |
| `session_id` | 业务 | Agent 多轮 |

```json
// Agent Run metadata 推荐字段
{
  "trace_id": "trc_...",
  "user_id": "usr_...",
  "session_id": "...",
  "skill": "..."
}
```

---

## 3. LiteLLM + Langfuse（默认）

### 3.1 Proxy 配置

```yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
```

### 3.2 环境变量（LiteLLM 进程）

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3.3 逻辑模型别名（推荐）

| 别名 | 用途 |
|------|------|
| `{product}-fast` | 解析、分类 |
| `{product}-writer` | 生成、改写 |
| `{product}-coach` | 对话、Agent |

业务传别名，不传厂商 model id；路由与 fallback 在 LiteLLM `config.yaml`。

---

## 4. FastAPI 侧（L1）

### 4.1 Middleware

- 读取或生成 `trace_id`
- 响应头 `X-Trace-Id`
- `contextvars` 绑定 structlog

### 4.2 日志字段

```json
{
  "trace_id": "trc_...",
  "actor_id": "usr_...",
  "event": "jobcome.profile.upload.completed",
  "duration_ms": 1200
}
```

**event 命名：** `{product}.{domain}.{action}`

### 4.3 隐私

| 记 | 不记 |
|----|------|
| id、token 数、tool 名 | 简历/JD 全文、密码、cookie |

---

## 5. SSE / 长连接

至少打 4 条日志：

- `sse.connect`
- `sse.first_token`
- `mcp.tool.call`（如有）
- `sse.done` / `sse.error`

---

## 6. 排障流程

1. 用户报 `X-Trace-Id`
2. Langfuse 搜 metadata `trace_id`
3. 日志系统搜同一 `trace_id`
4. 定位：API / Store / Adapter / LiteLLM / MCP

---

## 7. 项目覆盖

若用 Logfire、自建 Langfuse、或不用 Agent，在项目 `docs/工程规范.md` 覆盖表中说明。

JobCome 实例：[job-come/docs/可观测性与Trace.md](../../job-come/docs/可观测性与Trace.md)
