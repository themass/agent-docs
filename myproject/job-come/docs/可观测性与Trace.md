# JobCome 可观测性与 Trace 设计

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 状态 | **M1 冻结** |
| LLM 网关 | **LiteLLM Proxy** |
| 关联 | [基础设施与LLM.md](基础设施与LLM.md) · [技术方案.md](技术方案.md) |

---

## 1. 目标

| 要回答的问题 | 例子 |
|--------------|------|
| 用户一次操作卡在哪？ | 上传后解析 30s 没返回 |
| Agent 哪一步错了？ | 拔高后 Reviewer 没 pass |
| 花了多少钱、多少 token？ | 某用户本月 LLM 费用 |
| 能否按用户/会话回放？ | 模拟面试第 3 轮 tool 调错 |

**原则：**

- **一条 `trace_id` 贯穿** 浏览器 → FastAPI → DeerFlow → LiteLLM → MCP
- **LLM 明细走 LiteLLM 生态**（Langfuse），业务事件走 **结构化日志**
- **默认不落简历全文**到 trace（PII）；只记 id、字段 path、hash

---

## 2. 三层观测（不要混成一套）

```text
┌─────────────────────────────────────────────────────────────────┐
│ L1  请求追踪（OpenTelemetry / trace_id）                         │
│     HTTP、DB、Redis、OSS、SSE 耗时与错误                           │
├─────────────────────────────────────────────────────────────────┤
│ L2  LLM 追踪（LiteLLM → Langfuse）                               │
│     model、prompt/completion tokens、cost、latency、tool calls   │
├─────────────────────────────────────────────────────────────────┤
│ L3  产品审计（结构化日志 + 可选 MySQL jc_event）                  │
│     谁、何时、做了什么（登录、导出、记题），无 prompt 正文          │
└─────────────────────────────────────────────────────────────────┘
```

| 层 | M1 | M2+ |
|----|-----|-----|
| L1 | `trace_id` + structlog JSON；关键 span 手动 | OTel SDK → Jaeger/Tempo |
| L2 | LiteLLM callbacks → **Langfuse**（自托管） | + 成本大盘 |
| L3 | 日志 | `jc_event` 表 + 管理查询 |

---

## 3. 关联 ID 设计（冻结）

一次用户操作可能产生多条链路，用 **三个 ID** 区分：

| ID | 生成位置 | 格式 | 用途 |
|----|----------|------|------|
| **`trace_id`** | API 入口（无则生成） | `trc_{ulid}` | 全链路唯一；进日志、响应头、LiteLLM metadata |
| **`request_id`** | 同 `trace_id` 或子 span | 同上 | HTTP `X-Request-Id`（与 trace_id 相同即可，M1 不拆） |
| **`session_id`** | 业务层 | `sess_` / `mock_` / DeerFlow `thread_id` | Agent 多轮对话归属 |
| **`actor_id`** | 鉴权 | `usr_xxx` 或 `gst_xxx` | 租户维度查询 |

**传播路径：**

```text
Browser
  │  (可选) X-Request-Id
  ▼
FastAPI middleware → trace_id 写入 contextvars
  │
  ├─► structlog 每条日志带 trace_id, actor_id
  ├─► DeerFlowSessionClient.start(metadata={ trace_id, user_id, profile_id, session_id, skill })
  ├─► LiteLLM 请求头/metadata（经 DeerFlow 或直连时）
  └─► MCP tools：从 Run metadata 读 trace_id，日志带上

响应头（便于用户报障）：
  X-Trace-Id: trc_01J...
```

**DeerFlow Run metadata（冻结字段）：**

```json
{
  "trace_id": "trc_01J...",
  "user_id": "usr_xxx",
  "profile_id": "prof_xxx",
  "session_id": "resume_sess_xxx",
  "skill_hint": "resume-writer",
  "actor": "user"
}
```

MCP Server **只信 metadata**，与鉴权一致。

---

## 4. LiteLLM 侧 Trace（L2）

### 4.1 托管免费版 vs 自托管

| 方案 | 免费额度 | 要信用卡？ | 适合 JobCome M1 |
|------|----------|------------|-----------------|
| **[Langfuse Cloud Hobby](https://langfuse.com/pricing)** | **5 万 units/月**，30 天保留，2 用户 | ❌ 不需要 | ✅ LLM trace 够用；Agent 多 step 消耗 units 较快 |
| **[Logfire Personal](https://pydantic.dev/pricing)** | **1000 万 records/月**，30 天，1 席位 | ❌ 不需要 | ✅ 额度更大；FastAPI 全栈 OTel 更顺 |
| Langfuse 自托管 | 无 unit 上限 | — | 要维护 ClickHouse+PG，M1 不急 |

**没有「官方项目申请」流程**——直接注册 Cloud 账号即可（Hobby / Personal 都是公开免费档）。

| | Langfuse Cloud | Logfire Cloud |
|---|----------------|---------------|
| 注册 | [cloud.langfuse.com](https://cloud.langfuse.com) | [logfire.pydantic.dev](https://logfire.pydantic.dev) |
| LiteLLM 对接 | `success_callback: ["langfuse"]` | `success_callback: ["logfire"]` + `LOGFIRE_TOKEN` |
| 强项 | LLM trace UI、eval、prompt 版本 | **全链路 OTel**（API+DB+LLM 一条 trace） |
| 弱项 | 免费 units 对 Agent 偏紧 | 1 人免费席；团队要 $49/月起 |

**M1 建议（本机开发、不想自建）：** 使用 **Langfuse Cloud Hobby**（冻结，见 [工程规范.md](工程规范.md)）。

### 4.2 LiteLLM Proxy + Langfuse Cloud（冻结）

LiteLLM 原生支持 [Langfuse callback](https://docs.litellm.ai/docs/observability/langfuse_integration)；**不必在 JobCome 业务代码里 hook 每次 LLM 调用**。

```yaml
# deploy/litellm/config.yaml（片段）
litellm_settings:
  callbacks: ["langfuse"]
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

环境变量（LiteLLM 进程）：

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # 托管；自托管则填自己的 URL
```

LANGFUSE_HOST=https://cloud.langfuse.com
```

### 4.3 Logfire（不采用）

M1 不引入 Logfire；若将来评估全栈 OTel，另开 ADR。

### 4.4 把业务维度打进 Langfuse

DeerFlow / 适配层调用 LiteLLM 时，在 **metadata / tags** 里带：

| 字段 | 说明 |
|------|------|
| `trace_id` | 与 API 一致 |
| `user_id` | 计费、排障 |
| `profile_id` | 档案维度 |
| `session_id` | Agent 会话 |
| `skill` | `resume-writer` / `coach-mock` |
| `surface` | `elevate` / `agent_chat` / `mock` |

Langfuse / Logfire 里按 `user_id`、`skill` 过滤即可。

若 DeerFlow 暂不能透传 metadata，在 **`DeerFlowSessionClient`** 包一层：创建 run 前写入 metadata；或在 LiteLLM 侧用 **key-level metadata**（虚拟 key per skill）。

### 4.5 LiteLLM 自带日志（备选 / 补充）

| 能力 | 用途 |
|------|------|
| `store_model_in_db` + Postgres | 请求级 spend 入库 |
| Langfuse | **推荐**：trace UI、generation 回放、eval |

M1 **只上 Langfuse**，不重复建 LiteLLM Postgres spend 表（除非你要和 `vpn` 库报表合一）。

---

## 5. FastAPI 侧（L1 + L3）

### 5.1 中间件（M1）

```python
# 伪代码
@app.middleware("http")
async def trace_middleware(request, call_next):
    trace_id = request.headers.get("X-Request-Id") or new_trace_id()
    bind_context(trace_id=trace_id, path=request.url.path, method=request.method)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
```

### 5.2 结构化日志（structlog）

每条日志字段：

```json
{
  "ts": "2026-09-03T05:00:00Z",
  "level": "info",
  "trace_id": "trc_01J...",
  "actor_id": "usr_xxx",
  "event": "profile.upload.completed",
  "profile_id": "prof_xxx",
  "duration_ms": 1200,
  "bytes": 1048576
}
```

**事件命名（冻结前缀 `jobcome.`）：**

| event | 何时 |
|-------|------|
| `auth.login.success` | 登录成功 |
| `profile.upload.start` / `.completed` / `.failed` | 上传 |
| `resume.elevate.start` / `.completed` | 拔高 |
| `agent.session.start` | 开 Agent |
| `agent.sse.chunk` | 仅 debug 级别，生产关闭 |
| `mcp.tool.call` | MCP 工具名 + duration（无参数正文） |
| `export.job.completed` | 导出 |

### 5.3 敏感数据

| 记录 | 不记录 |
|------|--------|
| `profile_id`, 字段 path | 简历全文、邮箱、手机 |
| prompt **token 数** | prompt **正文**（Langfuse 可配置 mask） |
| tool 名、`duration_ms` | tool 参数里的 PII |

Langfuse：**开启 mask** 或只存 hash；生产默认少存 prompt 正文直到合规评审。Logfire：可用 [scrubbing](https://logfire.pydantic.dev/docs/how-to-guides/scrubbing/) 脱敏。

---

## 6. SSE / Agent 流

SSE 长连接在 trace 里算 **一个 HTTP span + 多个子事件**：

```text
trace_id=trc_01J
  span: POST /resume-agent/sessions          12ms
  span: deerflow.thread.create               45ms
  span: GET /resume-agent/sessions/.../events  (long)
      event: sse.first_token                  +800ms
      event: mcp.jobcome_profile_patch        +1200ms
      event: sse.done                         +45s
```

M1：在 `DeerFlowSessionClient.stream_events` 里打 **开始/首 token/结束/错误** 四条日志即可；M2 再接 OTel span。

---

## 7. MCP 工具 Trace

```python
# agent/mcp/tools/profile_patch.py
async def profile_patch(ctx, patch):
    log.info("mcp.tool.call", tool="profile_patch", trace_id=ctx.trace_id, ...)
    t0 = time.monotonic()
    try:
        result = await profile_service.apply_patch(...)
        log.info("mcp.tool.ok", duration_ms=..., fields_changed=len(patch))
        return result
    except Exception as e:
        log.error("mcp.tool.error", error=str(e))
        raise
```

`ctx` 从 MCP Run metadata 注入。

---

## 8. 可选表 `jc_event`（M2）

M1 可只用日志；若要 SQL 查审计：

```sql
CREATE TABLE jc_event (
  id          VARCHAR(32) PRIMARY KEY,
  trace_id    VARCHAR(32) NOT NULL,
  actor_id    VARCHAR(32) NULL,
  user_id     VARCHAR(32) NULL,
  event       VARCHAR(64) NOT NULL,
  resource_type VARCHAR(32) NULL,
  resource_id VARCHAR(32) NULL,
  meta        JSON NULL,
  created_at  DATETIME(3) NOT NULL,
  INDEX idx_trace (trace_id),
  INDEX idx_user_time (user_id, created_at),
  INDEX idx_event_time (event, created_at)
);
```

**不写 prompt；`meta` 仅小 JSON（如 `elevation_level`）。**

---

## 9. 部署拓扑（本机 → 服务器）

```text
本机开发
  jobcome-api  →  logs stdout (JSON)
  litellm      →  Langfuse docker :3001
  langfuse     →  自带 Postgres（可与业务 MySQL 分离）

生产 job.sspacee.com
  api / litellm / langfuse 均内网
  Langfuse UI 仅 VPN 或管理员 IP
  日志 → 文件/ Loki（可选）
```

Langfuse 自托管：

```bash
git clone https://github.com/langfuse/langfuse.git
# 按官方 docker-compose 起（独立 DB，不要和业务 vpn 混用 unless 你愿意）
```

---

## 10. M1 实施清单

| # | 任务 | 周 |
|---|------|-----|
| 1 | FastAPI `trace_id` middleware + `X-Trace-Id` | W0 |
| 2 | structlog JSON + `contextvars` | W0 |
| 3 | DeerFlow metadata 写入 `trace_id` / `user_id` / `profile_id` | W0 spike |
| 4 | LiteLLM callbacks → **Langfuse Hobby** 或 **Logfire Personal**（二选一） | W2 |
| 5 | MCP `mcp.tool.*` 日志 | W2 |
| 6 | （可选）Langfuse/Logfire 仅 Cloud，不自建 | W2 |
| 7 | OTel + Jaeger | M2 |

---

## 11. 排障手册（给用户/客服）

用户说「拔高失败了」：

1. 让用户 F12 看响应头 **`X-Trace-Id`**
2. Langfuse 搜 `trace_id`
3. 日志系统搜 `trace_id`
4. 看是 OSS、MCP、还是 LiteLLM 4xx/5xx

---

## 12. 文档索引

| 问题 | 章节 |
|------|------|
| 几层 trace | §2 |
| ID 怎么传 | §3 |
| LiteLLM 配 Langfuse | §4 |
| 日志记什么 | §5 |
| SSE Agent | §6 |
| 要不要建表 | §8 |
