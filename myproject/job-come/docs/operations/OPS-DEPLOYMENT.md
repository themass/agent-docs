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

### 服务器只需要 job-come 这一个目录

`agentkit`、`deerflow-harness`、`deerflow-extension-api` 三个包以**预编译 wheel**
的形式提交在 `backend/server/wheels/`（约 2.8MB），`pyproject.toml` 从这些 wheel 取源：

```toml
[tool.uv.sources]
agentkit = { path = "wheels/agentkit-0.1.0-py3-none-any.whl" }
```

所以部署机上：

```bash
cd backend/server && uv sync --frozen --no-dev --no-editable
```

就是一个普通的 Python 项目安装——**不需要 `libs/agentkit`、不需要 monorepo 源码、
不需要在意目录深度**。执行 `./scripts/install-production.sh` 即可，它跑的就是这条命令。

### 何时需要重建 wheel（在 dev 机器上）

改了 vendored DeerFlow 或 `libs/agentkit` 的源码之后：

```bash
./scripts/build-release.sh --update    # 重建 wheel + 改写版本 pin + 重新 lock
```

不重建的后果是**静默的**：装得上、import 得通，跑的还是旧代码。建议把这条接进 CI：

```bash
./scripts/build-release.sh --check     # 源码版本与 wheel 不符则失败
```

### 首次部署

先把 `job-come` 目录传到服务器（monorepo 没有可 `git clone` 的私有远端——
唯一配置的 `origin` 是公开的 `github.com/langchain-ai/deepagents` 上游，不是部署目标）：

```bash
# 在 dev 机器：
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '__pycache__' \
  /Users/gqli/work/deepagents/docs/myproject/job-come/ \
  user@server:/opt/jc/
```

```bash
# 在服务器：
cd /opt/jc
./scripts/install-production.sh        # uv sync --frozen，三个本地包从 wheels/ 解析
cp backend/server/.env.example backend/server/.env   # 然后填写生产配置
./scripts/start-production.sh          # migration + npm ci + build + 启动两个进程
```

`install-production.sh` **只装 Python 依赖**，不构建前端、不启动任何进程。
构建与启动在 `start-production.sh`：它按顺序做 Alembic migration、`npm ci`、
`npm run build`，再前台拉起 uvicorn 与 `next start`。

启动前它会先校验两件最容易出错且报错最晚的配置，不通过直接拒绝启动：

- `NEXT_PUBLIC_SITE_URL` 未设或是 localhost —— 否则构建出的 sitemap 与 canonical
  全指向 localhost，几周后才以「一条都没收录」的形式暴露
- `JC_COOKIE_SECURE` 与站点协议不匹配 —— https 站点配 `false` 会丢掉所有登录态，
  而症状（页面能开、登录不生效）离病因很远

### 常驻运行（推荐）

前台脚本适合首次部署与排障；长期运行用 `deploy/systemd/` 下的两个 unit，
分开托管两个进程（一个脚本同时持有两者时，任一崩溃会带走另一个）：

```bash
sudo cp deploy/systemd/jc-{api,web}.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now jc-api jc-web
```

unit 里的 `WorkingDirectory`、`User`、venv 路径按目标机器修改；密钥仍只在
`backend/server/.env`，由 `EnvironmentFile` 加载，不入仓库。

### 发布一次新版本

job-come 没有独立 git 仓库，是嵌在 deepagents monorepo 里的一个目录，而该
monorepo 唯一配置的远端是公开的 `github.com/langchain-ai/deepagents`——那是
上游开源项目，不是部署目标，不能也不该往那推送。代码走 `rsync` 到服务器。

```bash
# 在 dev 机器（改过 vendored DeerFlow / agentkit 的话先跑 build-release.sh --update）：
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '__pycache__' \
  . user@server:/opt/jc/
```

```bash
# 在服务器：
cd /opt/jc
./scripts/install-production.sh
./scripts/start-production.sh --build-only
sudo systemctl restart jc-api jc-web
```

**`--build-only` 不能省。** `next start` 读的是 `.next` 目录，不重新构建就
`systemctl restart`，服务会静默继续提供上一个版本——没有任何报错。

### 验证

```bash
curl -sf http://127.0.0.1:8000/health && echo API-OK
curl -sI http://jc.sspacee.com/ | head -1
curl -s http://jc.sspacee.com/sitemap.xml | head -5    # 确认不是 localhost
```

随后对登录、上传、导出、Agent、邮件做 smoke test（见 [`QA-TESTING.md`](QA-TESTING.md)）。

### 端口约定

`3000`（web）与 `8000`（API）在四处必须一致：Nginx 的 `upstream`、
`start-production.sh` 的默认值、两个 systemd unit。改一处就要改四处。
注意 **dev 的 API 端口是 8001**（`dev.sh`），与生产不同，这是有意的——
本地起着 dev 时不会占用生产端口。

## 3. 必需环境配置

| 类别 | 关键配置 |
|---|---|
| 应用 | `JC_ENV=production`、`JC_PUBLIC_URL=http://jc.sspacee.com`、`JC_API_PREFIX=/api/v1` |
| 前端 | `NEXT_PUBLIC_SITE_URL`（已提交在 `frontend/web/.env.production`，当前 `http://jc.sspacee.com`）。**构建期生效**：改完必须重新 `npm run build`，重启不生效 |
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
