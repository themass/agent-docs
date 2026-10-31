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

三个脚本覆盖全部日常操作：`deploy.sh`（装依赖、跑 migration、构建前端，不启动任何进程）、
`backend.sh`、`frontend.sh`（各自 `start|stop|restart|status`，PID 文件追踪，**不需要
systemd、不需要 sudo**——两者都基于 PID 文件自行管理进程，这也是实际部署环境
（无 sudo 权限的云主机）验证过的路径）。

### 服务器只需要 job-come 这一个目录

`agentkit`、`deerflow-harness`、`deerflow-extension-api` 三个包以**预编译 wheel**
的形式提交在 `backend/server/wheels/`（约 2.8MB），`pyproject.toml` 从这些 wheel 取源，
所以 `deploy.sh` 跑的 `uv sync --frozen --no-dev --no-editable` 是一次普通的 Python
项目安装——**不需要 `libs/agentkit`、不需要 monorepo 源码、不需要在意目录深度**。

改了 vendored DeerFlow 或 `libs/agentkit` 源码之后，在**有完整 monorepo 的机器**上：

```bash
./scripts/build-release.sh --update    # 重建 wheel + 改写版本 pin + 重新 lock
```

不重建的后果是**静默的**：装得上、import 得通，跑的还是旧代码。`--check` 只校验不重建，
适合接进 CI。

### Python 3.12（唯一需要关心的运行时前置）

项目要求 `>=3.12,<3.13`。部署机的 `python3` 常常更旧（Ubuntu 20.04 是 3.10，CentOS 8 是 3.6），
但**不要去升级系统解释器**：apt/yum 自己的工具链绑在它上面，换掉会在别处、在之后才炸。

`deploy.sh` 的处理是：先找已有的 uv 3.12，找不到就让 `uv python install 3.12` 装一份私有的到用户目录，
再把项目 venv 建在这份解释器上（`scripts/lib/python_env.sh`）。全程不碰系统 Python，也不需要 sudo。

想让这个用户的 `python3` 直接就是 3.12（例如以后手动跑脚本），加一次 `--python-default`：

```bash
./scripts/deploy.sh --python-default
```

它在 `~/.local/bin` 写 shim。**已经打开的 shell 不会生效**，需要 `source ~/.local/bin/env` 或重新登录；
新窗口就是 3.12。这是一个纯用户级 PATH 变更，删掉那个目录即可撤销。

`backend.sh start` 会打印实际使用的解释器和版本，并在 venv 不是 3.12 时直接报错退出，
而不是等到某个依赖 import 失败才暴露。

### 首次部署

job-come 没有独立 git 仓库，是嵌在 deepagents monorepo 里的一个目录，而该 monorepo
唯一配置的远端是公开的 `github.com/langchain-ai/deepagents`——那是上游开源项目，
不是部署目标，不能也不该往那推送。代码走 `rsync` 到服务器：

```bash
# 在 dev 机器：
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '__pycache__' \
  /Users/gqli/work/deepagents/docs/myproject/job-come/ \
  user@server:/opt/jc/
```

```bash
# 在服务器：
cd /opt/jc
cp backend/server/.env.example backend/server/.env   # 然后填写生产配置
./scripts/deploy.sh
./scripts/backend.sh start
./scripts/frontend.sh start
```

`deploy.sh` 启动前会校验 `NEXT_PUBLIC_SITE_URL`（未设或是 localhost 就拒绝构建——
否则生成的 sitemap/canonical 全指向 localhost，几周后才以「一条都没收录」的形式暴露）；
`backend.sh start` 启动前会校验 `JC_COOKIE_SECURE` 与 `JC_PUBLIC_URL` 协议是否一致
（不一致要么丢登录态要么浏览器直接拒收 cookie）。两者都不通过就直接报错退出，不会
带着错误配置硬启动。

`start` 会自检：`backend.sh` 轮询 `/health` 最多 30s，`frontend.sh` 轮询首页响应，
失败会打印最近日志并以非零退出——不会把"进程起来了"误报成"服务正常"。

### 发布一次新版本

```bash
# 在 dev 机器（改过 vendored DeerFlow / agentkit 的话先跑 build-release.sh --update）：
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '__pycache__' \
  . user@server:/opt/jc/
```

```bash
# 在服务器：
cd /opt/jc
./scripts/deploy.sh
./scripts/backend.sh restart
./scripts/frontend.sh restart
```

`restart` 内部是「先 stop 再 start」，同样带自检；`deploy.sh` 不能省——`next start`
读的是 `.next` 目录，不重新构建就 `restart`，服务会静默继续提供上一个版本，没有
任何报错。

### 日常运维

```bash
./scripts/backend.sh status     # 或 frontend.sh status
```

日志固定在 `.data/logs/production/{api,web}.log`；PID 文件在 `.data/run/{api,web}.pid`。

### 验证

```bash
./scripts/backend.sh status && ./scripts/frontend.sh status
curl -sf http://127.0.0.1:8000/health && echo API-OK
curl -sI http://jc.sspacee.com/ | head -1
curl -s http://jc.sspacee.com/sitemap.xml | head -5    # 确认不是 localhost
```

随后对登录、上传、导出、Agent、邮件做 smoke test（见 [`QA-TESTING.md`](QA-TESTING.md)）。

### 端口约定

`3000`（web）与 `8000`（API）在三处必须一致：Nginx 的 `upstream`、
`backend.sh`/`frontend.sh` 的默认值（`JC_API_PORT`/`JC_WEB_PORT` 可覆盖）。改一处就要改三处。
注意 **dev 的 API 端口是 8001**（`dev.sh`），与生产不同，这是有意的——
本地起着 dev 时不会占用生产端口。

### 一个真实踩过的坑：不要用 `$!` 追踪 `next start` 的 PID

`next start` 的 CLI 进程会 fork 出真正长期运行的 `next-server`，然后**自己退出**——
`$!` 捕获到的是那个已经退出的 launcher PID，而不是真正监听端口、一直存活的进程。
实测复现：健康检查第一次能通过（此时 launcher 还没退出），但几秒后用 `$!` 再查就会
误判成"进程已死"，即使服务其实一直在正常响应。`uvicorn` 没有这个问题（master 进程
整个生命周期都存在，不会中途交接退出）。`frontend.sh` 的修法是健康检查通过后用
`lsof -t -iTCP:$PORT -sTCP:LISTEN` 反查端口上真正的监听 PID，而不是信任 `$!`
（见 `scripts/lib/daemon.sh` 的 `daemon_start`）。

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
