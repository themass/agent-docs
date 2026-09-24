# JobCome 生产部署要点

## 1. 拓扑（推荐）

```text
用户浏览器
    → Nginx（单域 HTTPS，如 job.sspacee.com）
        → /          → Next.js (apps/web)
        → /api/v1/*  → uvicorn (jobcome)
```

**同一域名**承载前端与 API，Cookie `jc_session` / `jc_guest` 无需跨域。

## 2. 环境变量（生产）

| 变量 | 说明 |
|------|------|
| `JOB_COME_PUBLIC_URL` | 前端公网 URL（邮件链接） |
| `JOB_COME_COOKIE_SECURE=true` | HTTPS 必须 |
| `JOB_COME_LLM_ENABLED=true` | 生产开 LLM |
| `JOB_COME_CDN_SIGN_KEY` | 备案前留空，用 TOS 预签名 |

完整列表见 `.env.example`。

## 3. Nginx 片段（示例）

```nginx
server {
    listen 443 ssl;
    server_name job.sspacee.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }
}
```

## 4. 进程

- **API**：`uvicorn jobcome.main:app --host 127.0.0.1 --port 8000 --workers 2`
- **Web**：`npm run build && npm start` 或 PM2

## 5. 数据库

- MySQL 表前缀 `jc_*`（与 vpn 库共用或独立 schema）
- Redis：session + 邮件 token
- 备份：每日 `jc_profile` / `jc_user` 快照

## 6. 可选 MCP（默认关闭）

在服务器上启用外部 MCP 前阅读 `docs/开源集成指南.md`。生产建议仅开 `jobcome` MCP，其余按需。

## 7. 上线检查清单

- [ ] `curl /health` OK
- [ ] `./scripts/e2e_smoke.sh` 全绿
- [ ] SMTP 发信测试
- [ ] TOS 上传 + 预签名下载
- [ ] `JOB_COME_COOKIE_SECURE=true`
