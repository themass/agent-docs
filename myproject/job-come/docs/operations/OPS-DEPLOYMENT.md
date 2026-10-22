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

主站和 API 必须使用同一域名下的相对 `/api/v1`，避免生产跨域与 cookie 域问题。当前对外地址为 `http://jc.sspacee.com`；切换 HTTPS 见下节。

## 1.1 切换 HTTPS

参考配置已备好：`backend/server/nginx/jc.sspacee.com.https.conf`（含 80→443 301 跳转与 ACME 续期放行）。

**证书必须由公共 CA 签发。** 自签名证书在公网站点上不成立：浏览器整页拦截，Googlebot 与 Baiduspider 直接拒绝握手——结果不是排名下降，是完全抓不到。内网自签名那套经验在这里不适用。

签发方式三选一，都免费：

| 方式 | 适用 | 有效期 |
|---|---|---|
| Let's Encrypt + certbot | 服务器 80/443 公网可达 | 90 天，自动续期 |
| 阿里云 / 腾讯云免费 DV 证书 | 域名或服务器在该云商 | 3 个月～1 年，手动换 |
| 云厂商负载均衡托管证书 | 已有 SLB/CLB | 自动 |

certbot 路径：

```bash
certbot certonly --webroot -w /var/www/certbot -d jc.sspacee.com
```

**四处必须同时改**，漏掉任何一处都会留下难查的半截状态：

1. Nginx 换成 `jc.sspacee.com.https.conf`，`nginx -t && nginx -s reload`
2. `frontend/web/.env.production` → `NEXT_PUBLIC_SITE_URL=https://jc.sspacee.com`，
   **然后重新 `npm run build`**（构建期变量，重启不生效）
3. `backend/server/.env` → `JC_COOKIE_SECURE=true`、`JC_PUBLIC_URL=https://jc.sspacee.com`
4. 搜索引擎后台：Google Search Console 把 `http://` 与 `https://` 视为两个不同资源，
   需重新添加 https 资源并重新提交 sitemap（建议改用 DNS 验证的「网域」资源，一次覆盖两者）；
   百度资源平台同样需要重新验证与提交

漏掉第 3 项的症状是页面能开但登录态持续丢失（Secure cookie 未下发）；漏掉第 2 项的症状是 canonical 与 sitemap 仍指向 http，搜索引擎看到的正式地址和实际服务的不一致。

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
| 前端 | `NEXT_PUBLIC_SITE_URL`（已提交在 `frontend/web/.env.production`，当前 `http://jc.sspacee.com`）。**构建期生效**：改完必须重新 `npm run build`，重启不生效 || MySQL | `JC_DB_*`，并确认 schema migration 成功 |
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
