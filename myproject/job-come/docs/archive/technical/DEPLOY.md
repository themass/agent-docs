# JC 生产部署要点

## 1. 拓扑（推荐）

```text
用户浏览器
    → Nginx（单域 HTTP 灰度，如 jc.sspacee.com）
        → /          → Next.js (frontend/web)
        → /api/v1/*  → uvicorn (jc)
```

**同一域名**承载前端与 API，Cookie `jc_session` / `jc_guest` 无需跨域。

## 2. 环境变量（生产）

| 变量 | 说明 |
|------|------|
| `JC_PUBLIC_URL` | 前端公网 URL（邮件链接） |
| `JC_COOKIE_SECURE=false` | 当前 HTTP 灰度环境必须；正式 HTTPS 时改为 `true` |
| `JC_LLM_ENABLED=true` | 生产开 LLM |
| `JC_DEERFLOW_RUNTIME_HOME=.data/deerflow/runtime` | Harness 生成的 session / skill-projection 状态；不使用项目根 `.deer-flow` |
| `JC_CDN_SIGN_KEY` | 备案前留空，用 TOS 预签名 |

完整列表见 `backend/server/.env.example`。

## 3. Nginx 片段（示例）

```nginx
server {
    listen 80;
    server_name jc.sspacee.com;

    location /api/v1/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;  # Agent SSE
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }
}
```

## 4. 安装与进程

生产安装使用锁定的 vendored DeerFlow 源码并关闭 editable：

```bash
./scripts/install-production.sh
```

- **API**：`uvicorn jc.main:app --host 127.0.0.1 --port 8000 --workers 1`（同一进程提供 API 与嵌入的 DeerFlow Harness；当前使用进程内锁与本地 SQLite checkpoint）
- **Web**：`cd frontend/web && npm run build && npm start` 或 PM2
- **不额外启动 DeerFlow 服务**：它是锁定的 vendor 依赖，由 API 进程加载。

## 5. 数据库

- MySQL 表前缀 `jc_*`（与 vpn 库共用或独立 schema）
- Redis：所有 key 必须为 `jc:{env}:{namespace}:{identifier}`，例如生产环境 `jc:prod:session:{id}`。
- TOS：所有新对象 key 必须为 `jc/{env}/...`，例如 `jc/prod/profiles/{profile_id}/source/{source_id}.pdf`。
- 备份：每日 `jc_profile` / `jc_user` 快照

## 6. 可选 MCP（默认关闭）

在服务器上启用外部 MCP 前阅读 `docs/开源集成指南.md`。生产建议仅开 `jc` MCP，其余按需。

## 7. 上线检查清单

- [ ] `curl /health` OK
- [ ] `./scripts/e2e_smoke.sh` 全绿
- [ ] SMTP 发信测试
- [ ] TOS 上传 + 预签名下载
- [ ] 当前 HTTP 灰度：`JC_COOKIE_SECURE=false`
- [ ] 正式开放真实用户前：切换 HTTPS，并设置 `JC_COOKIE_SECURE=true`
