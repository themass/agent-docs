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

## 1.1 HTTPS（http 与 https 同时可用）

线上 `http://jc.sspacee.com` 与 `https://jc.sspacee.com` 都提供服务，不做跳转。这是有意的选择，
由此得出两条约束：

- **`JC_COOKIE_SECURE` 保持 `false`**。设成 `true` 后通过 http 访问的用户拿不到登录 cookie，登录会静默失效。
- **`JC_PUBLIC_URL` 保持 `http://jc.sspacee.com`**，邮件里的重置和验证链接都指向 http，两种访问方式都能完成登录。

证书由 Let's Encrypt 签发：

```bash
sudo /etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh      # 释放 80 端口
sudo certbot certonly --standalone -d jc.sspacee.com
sudo /etc/letsencrypt/renewal-hooks/deploy/start-nginx.sh
```

签发后 `apply-nginx-conf.sh` 会自动引用 `/etc/letsencrypt/live/jc.sspacee.com/`（需要证书包含该域名且未过期），
否则退回自签证书。续期由 `certbot.timer` 自动完成（到期前 30 天内），沿用同一套钩子。
钩子里的 `nginx -s stop` 没有指定配置文件，续期前应确认它能停掉实际运行的 nginx（见 1.2 的 pid 说明）。

证书续期后 nginx 需要重载才会读到新文件，`apply-nginx-conf.sh` 的 `live/` 路径是符号链接，续期后只需 `nginx -s reload`。

搜索引擎：http 与 https 是两个资源，Google Search Console、百度资源平台需要分别验证；建议在 Search Console
使用 DNS 验证的「网域」资源，一次覆盖两者。

## 1.2 Nginx：两个脚本（root）

所有机器的 nginx 目录一致：

```text
/root/local/nginx                 → 软链到 /root/local/nginx-<版本>
/root/local/nginx/conf/nginx.conf # 只做一件事：include conf/server/*.conf
/root/local/nginx/conf/server/    # 每个站点一个文件；我们的是 jc-upstreams / jc-site-http / jc-site-https
/root/local/nginx/ssl/            # 我们的自签证书
```

**1. 机器上没有 nginx：编译安装（每台机器一次）**

```bash
sudo ./scripts/nginx/build-nginx.sh
```

下载校验（损坏的压缩包会重新下载）、编译、建软链、建目录、写 `nginx.conf`。已经装好的机器上再运行
不会重新编译，也不会改软链；`--force` 才会原地重建同版本。**它不写任何站点**。

**2. 配置变更：测试并重载（新装的和已有 nginx 的机器都一样）**

```bash
sudo ./scripts/nginx/apply-nginx-conf.sh              # 测试通过后 reload（没在运行就 start）
sudo ./scripts/nginx/apply-nginx-conf.sh --restart    # 测试通过后 stop 再 start
```

只写 `conf/server/` 下我们自己的三个文件和 `ssl/` 里的证书，别的站点和 `nginx.conf` 不动。
整个变更是**要么全部生效、要么原样退回**：`nginx -t` 不通过，或者 nginx 实际上不会加载这些文件，
就把原来的文件放回去，不重载，共用这个 nginx 的其它站点不受影响。

可调项（用 `sudo -E` 或 `sudo VAR=值 ...` 传进去）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `JC_NGINX_SERVER_NAME` | `jc.sspacee.com` | 一个或多个域名/IPv4，空格或逗号分隔；全部写入 `server_name` 和证书，第一个为主域名 |
| `JC_NGINX_HTTPS_PORT` | `443` | 被别的程序占用时自动只配 HTTP 并给出警告；用别的端口要在云安全组放行 |
| `JC_WEB_PORT` / `JC_API_PORT` | `3000` / `8000` | 上游端口 |
| `JC_NGINX_DEFAULT_SERVER` | 关 | 共用 nginx 上通常别的站点已经有 `default_server`，同一端口两个会让 `nginx -t` 失败 |

- 新增域名时证书会自动重签；已经覆盖全部域名的证书不会被替换（浏览器里信任过的证书不会每次变）。
- `http2` 的写法按这台机器的 nginx 版本自动选（1.25.1 起是 `http2 on;`）。
- 机器上别的服务也有自己的自签 HTTPS，没有冲突：证书按站点分开，靠 `server_name`（SNI）区分。
- 手写的 `nginx.conf` 如果没有 `include .../conf/server/*.conf;`，`apply-nginx-conf.sh` 会拒绝并告诉你
  要加哪一行，而不是写一个看起来部署了、实际不生效的站点。

**换机器**：域名和目录不变，在新机器上依次运行这两个脚本即可。只拷贝 `conf/server/` 不够，
站点文件用绝对路径引用 `/root/local/nginx/ssl` 里的证书，没有证书 `nginx -t` 会报找不到证书；运行脚本会生成。

**自签证书的限制**：浏览器会警告，搜索引擎抓取和 AdSense 都不友好（见 1.1）。面向公众和做 SEO、广告的页面
请继续用 HTTP 域名，或按 1.1 换公共 CA 证书。`JC_COOKIE_SECURE` 保持 `false`：设成 `true` 后通过 http
访问就收不到登录 cookie，登录会静默失效。

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

### 代码放在哪里，怎么到那里

仓库克隆在服务器上的任意位置（`~/work/agent-docs`），服务**不从克隆里运行**，运行目录是
`/home/web/webroot/job-come`（`JC_DEPLOY_DIR` 可改）。两者之间用 `scripts/publish.sh` 同步，由 web 用户运行：

```bash
cd ~/work/agent-docs && git pull --ff-only
cd myproject/job-come
./scripts/publish.sh --dry-run     # 先看会新增、修改、删除哪些文件
./scripts/publish.sh               # 同步
```

- 复制的是 **git 已跟踪的文件**（当前提交），所以不会带 `.git`、`node_modules`、没提交的临时文件；
  有未提交的改动会拒绝，`--allow-dirty` 才按磁盘上的现状复制，并在 `.deploy-version` 里注明。
- 只删除**上一次发布放进去、这次提交里已经没有**的文件（清单在 `.deploy-manifest`）。目标目录自己生成的
  `backend/server/.env`、`.venv`、`frontend/web/node_modules`、`.next`、`.data` 永远不在清单里，不会被碰。
- 不能用 root 运行（root 复制出来的文件 web 用户更新不了）。

### 新机器：先备环境

web 用户直接运行，不需要 sudo：

```bash
./scripts/deploy.sh --env-only
```

缺 `uv`、Python 3.12、Node 20 就装到当前用户的家目录里；已经够用的不动。只有 `curl`、`tar`、`gzip`、`lsof`
要管理员装，缺的会一次列全并给出 `apt-get install` 命令。`frontend.sh` 自己会把 `~/.local/node` 加进 PATH，
不需要改 `.bashrc`。网络受限时用 `JC_NODE_DIST_URLS` 换 Node 镜像，`UV_INSTALLER_GITHUB_BASE_URL` 换 uv 的下载源。

`deploy.sh` 还会检查 PDF 导出需要的两样东西，缺哪样就停下并给出要执行的命令（需要管理员）：

- **Chromium 的系统库**：`sudo apt-get install -y libxkbcommon0 libgbm1`。脚本会实际启动一次浏览器来验证。
- **中文字体**：`sudo apt-get install -y fonts-noto-cjk && sudo fc-cache -f`。没有中文字体时 PDF 里的中文无法提取，导出会失败。

### 首次部署

```bash
# web 用户，在克隆里：
./scripts/publish.sh
cd /home/web/webroot/job-come
cp backend/server/.env.example backend/server/.env   # 或从旧部署拷过来，填写生产配置
./scripts/deploy.sh --skip-frontend                  # 前端产物另传，见下
./scripts/backend.sh start
./scripts/frontend.sh start
```

服务器内存小（不到 1GB）时，`next build` 要跑半小时以上，建议在别处构建后把 `.next` 打包传来：
解压到 `frontend/web/` 即可，之后 `deploy.sh` 加 `--skip-frontend` 跳过构建。依赖也同理：
`JC_SKIP_NPM_CI=1` 使用已经解压好的 `node_modules`。

`deploy.sh` 启动前会校验 `NEXT_PUBLIC_SITE_URL`（未设或是 localhost 就拒绝构建——
否则生成的 sitemap/canonical 全指向 localhost，几周后才以「一条都没收录」的形式暴露）；
`backend.sh start` 启动前会校验 `JC_COOKIE_SECURE` 与 `JC_PUBLIC_URL` 协议是否一致
（不一致要么丢登录态要么浏览器直接拒收 cookie）。两者都不通过就直接报错退出，不会
带着错误配置硬启动。

`start` 会自检：`backend.sh` 轮询 `/health` 最多 30s，`frontend.sh` 轮询首页响应，
失败会打印最近日志并以非零退出——不会把"进程起来了"误报成"服务正常"。

**从旧位置迁移**：旧目录里的服务占着 3000/8000，新目录的服务起不来。先在旧目录
`./scripts/backend.sh stop && ./scripts/frontend.sh stop`，再按上面首次部署做。`.venv` 里的脚本写死了
绝对路径，不能搬，`deploy.sh` 会在新位置重建；`.env` 直接拷。想保留对话的 checkpoint，
同时拷 `backend/server/.data/`（其中 `.data/deerflow`）。

### 发布一次新版本

```bash
# web 用户，在克隆里（改过 vendored DeerFlow / agentkit 的话先在有完整 monorepo 的机器上跑 build-release.sh --update）：
git pull --ff-only
./scripts/publish.sh --deploy --restart
```

等价于 `publish.sh` 之后在运行目录里依次执行 `deploy.sh`、`backend.sh restart`、`frontend.sh restart`。
`--deploy` 后面用 `--` 给 `deploy.sh` 传参，例如 `./scripts/publish.sh --deploy -- --skip-frontend`。

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

`3000`（web）与 `8000`（API）是默认值。**本机的实际端口写在 `<部署目录>/.data/deploy.env`**，
例如 `JC_WEB_PORT=3001`。`backend.sh`、`frontend.sh`、`apply-nginx-conf.sh` 都读这个文件，所以
不带环境变量、不带 `sudo -E`、cron 里运行，结果一致；环境变量仍可临时覆盖。改了端口后必须重新运行
`apply-nginx-conf.sh`，否则 nginx 还指向旧端口。

注意 **dev 的 API 端口是 8001**（`dev.sh`），与生产不同，这是有意的——
本地起着 dev 时不会占用生产端口。

启动前会检查端口：被其它程序占用时直接拒绝启动，并打印占用者的 PID、命令和工作目录。
停止前会核对进程命令行，不会误杀别的服务。

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
| 模拟面试 | 迁移 `019_mock_interview_quota` 已执行（`deploy.sh` 会执行）；`deerflow/config.yaml` 含 `jc-reviewer` 模型，且 `routing.yaml` 含 `reviewer` 场景；改动后重启 backend |
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
