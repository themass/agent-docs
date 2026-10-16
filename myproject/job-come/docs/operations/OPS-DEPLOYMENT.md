# OPS-DEPLOYMENT：部署规范

- **状态**：V1 生产部署依据
- **最后更新**：2026-10-15

## 1. 目标拓扑

```text
http://jc.sspacee.com
  └─ Nginx
      ├─ /        → Next.js Web
      └─ /api/v1/ → FastAPI + embedded DeerFlow Agent
```

主站和 API 必须使用同一域名下的相对 `/api/v1`，避免生产跨域与 cookie 域问题。当前对外地址为 `http://jc.sspacee.com`；若切换 HTTPS，需同步启用 `JC_COOKIE_SECURE=true` 并校验 Nginx 代理头和重定向。

## 2. 生产构建与启动

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/install-production.sh
```

该脚本使用锁文件进行非 editable 安装；DeerFlow 源码来自锁定的 vendor 目录。随后：

1. 创建 `backend/server/.env` 并写入生产配置；
2. 在 `backend/server/` 运行 Alembic migration；
3. 构建 `frontend/web`：`npm ci && npm run build`；
4. 以进程管理器启动 FastAPI 和 Next.js；
5. 由 Nginx 代理 `/` 与 `/api/v1/`；
6. 对健康检查、登录、上传、导出、Agent、邮件做上线后 smoke test。

具体 systemd/进程管理命令应随目标服务器运行时固化在部署配置中，不应把密钥写入仓库。

## 3. 必需环境配置

| 类别 | 关键配置 |
|---|---|
| 应用 | `JC_ENV=production`、`JC_PUBLIC_URL=http://jc.sspacee.com`、`JC_API_PREFIX=/api/v1` |
| MySQL | `JC_DB_*`，并确认 schema migration 成功 |
| Redis | `JC_REDIS_URL`、`JC_REDIS_KEY_PREFIX=jc:prod:` |
| TOS | endpoint、bucket、region、AK/SK，写入 `jc/prod/` |
| LLM | `JC_LLM_ENABLED`、路由配置、供应商 API key/模型 slug |
| 邮件 | SMTP、发件人、重置与验证链接 |
| Session | `JC_COOKIE_SECURE`、TTL、反向代理可信头 |
| 可观测性 | Langfuse（可选）、日志、错误告警、容量指标 |

## 4. 发布门禁

部署不等于发布完成。必须通过 [`QA-TESTING.md`](QA-TESTING.md) 中的真实依赖 E2E、动态浏览器、文档解析、导出质量、隔离、备份和回滚检查后，才可批准上线。

## 5. 回滚原则

- 使用可识别的构建版本和锁定依赖；
- 数据库 migration 先审查可逆性，必要时备份后发布；
- 保留上一版前端和服务端启动产物；
- 出现权限、导出或数据完整性问题时优先停止相关入口，保留审计证据，再执行回滚。
