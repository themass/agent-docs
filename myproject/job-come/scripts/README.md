# JC Scripts

脚本分三类：服务器上由 web 用户运行的、服务器上由 root 运行的（Nginx）、开发机上的。
所有脚本按自己所在位置找路径，目录搬走不用改。

## 服务器：web 用户

日常发布：在克隆里 `git pull --ff-only && ./scripts/publish.sh --deploy --restart`。

| 脚本 | 做什么 |
|---|---|
| `publish.sh` | 把 git 已提交的代码同步到 `/home/web/webroot/job-come`（`JC_DEPLOY_DIR` 可改）。只删上次发布放进去、这次已经没有的文件；目标自己生成的 `.env`、`.venv`、`node_modules`、`.next`、`.data` 不碰。`--dry-run` 先看差异；`--deploy` / `--restart` 接着在目标目录跑 `deploy.sh` 和重启，`--` 之后的参数传给 `deploy.sh`。不能用 root |
| `deploy.sh` | 装 Python 依赖（三个本地包从 `backend/server/wheels/*.whl` 装，不需要 monorepo）、跑数据库迁移、装前端依赖并构建。**不启动任何进程**。`--skip-backend` / `--skip-frontend` 只做一半；`--python-default` 额外把 3.12 设为该用户的 `python3`；`JC_SKIP_NPM_CI=1` 使用已解压好的 `node_modules`。需要 Python 3.12，系统的不动，缺时由 `uv` 装一份 |
| `backend.sh start\|stop\|restart\|status` | 管理 API 进程（uvicorn），PID 文件追踪，不依赖 systemd 和 sudo。`start` 会轮询 `/health` 最多 30 秒，失败打印日志并以非零退出 |
| `frontend.sh start\|stop\|restart\|status` | 管理 Web 进程（`next start`）。`next start` 会把 `$!` 对应的进程换掉，所以用 `lsof` 反查端口上真正监听的 PID |
| `db_upgrade.sh` | 单独执行数据库迁移（`deploy.sh` 已经包含这一步） |
| `prune_llm_log.sh` | 按留存窗口清理 LLM 调用审计日志（里面是简历原文，必须定期清）。用 cron 跑：`17 4 * * * cd /home/web/webroot/job-come && ./scripts/prune_llm_log.sh >> .data/logs/production/prune.log 2>&1`。`JC_PRUNE_DRY_RUN=1` 只报数不删 |

Python 解释器依次找：`JC_PYTHON`、monorepo 的 `venv`、`backend/server/.venv`。

## 服务器：root（Nginx）

配置放在 `/root/local/nginx/conf/server/`，详见 [`docs/operations/OPS-DEPLOYMENT.md`](../docs/operations/OPS-DEPLOYMENT.md) 1.2。

| 脚本 | 做什么 |
|---|---|
| `sudo nginx/build-nginx.sh` | **每台机器一次**：编译安装 nginx 到 `/root/local/nginx-<版本>`，建软链 `/root/local/nginx`，写 `nginx.conf`（只 include `conf/server/*.conf`）。已装好的机器不重编译、不改软链，手写的 `nginx.conf` 不动。不写任何站点 |
| `sudo nginx/apply-nginx-conf.sh` | **配置变更时**：写入站点文件，`nginx -t` 通过且确认 nginx 会加载后重载（`--restart` 为 stop 再 start）。失败原样退回，不影响同一 nginx 上的其它站点。`JC_NGINX_SERVER_NAME` 可填多个域名，`JC_NGINX_HTTPS_PORT` 指定 HTTPS 端口 |

`nginx/lib.sh` 是这两个脚本共用的函数，被 `source`，不直接运行。

## 开发机（在 monorepo 里）

| 脚本 | 做什么 |
|---|---|
| `setup-venv.sh` | 把后端依赖装进 monorepo 的 `venv`（`dev.sh` 首次启动也会自动调用） |
| `dev.sh` | 启动本地 API、Web 和内嵌 Agent；输出同时写到 `.data/logs/dev/`。缺依赖时自动 `uv sync` |
| `test-local.sh` | 提交前检查：Python 字节码编译、后端测试、所有 shell 脚本语法、前端生产构建。不碰任何真实服务 |
| `build-release.sh --update` | 改了 vendored DeerFlow 或 `libs/agentkit` 源码后**必须**跑：重建 `backend/server/wheels/` 里的三个 wheel，同步 `pyproject.toml` 的版本并重新 lock。不跑的话服务器装上去的是旧代码，而且不报错。`--check` 只校验不重建。必须在 monorepo 里运行 |
| `sync-deerflow-upstream.sh` | 维护动作：同步 vendored DeerFlow。不是日常步骤 |

```bash
cd docs/myproject/job-come        # 从 monorepo 根目录进入
./scripts/setup-venv.sh           # 首次或依赖变更时
cp backend/server/.env.example backend/server/.env   # 首次
./scripts/dev.sh                  # 终端 1：API + Web
./scripts/test-local.sh           # 终端 2：检查
```

`dev.sh` 默认启动 Web `http://127.0.0.1:3000`、API `http://127.0.0.1:8000/api/v1`。Agent 内嵌在 API 进程里，不需要第三个服务。

## lib/

被其它脚本使用的辅助文件，不直接运行：

| 文件 | 用途 |
|---|---|
| `project_paths.sh` | 找项目目录和 Python 解释器 |
| `ensure_python_env.sh` | 缺依赖时调用 `setup-venv.sh` |
| `python_env.sh` | 找或安装 Python 3.12（`deploy.sh` 用） |
| `daemon.sh` | PID 文件管理（`backend.sh`、`frontend.sh` 用） |
| `run_with_heartbeat.sh` | 长命令执行时每隔一段时间打印一行（`deploy.sh` 用，防 SSH 断开） |
| `bootstrap.py` | `prune_llm_log.py` 用来选对解释器和加 `sys.path` |
| `log_output.py` | `dev.sh` 用来给日志加时间戳、轮转 |

## 本地开发日志

`./scripts/dev.sh` 的输出同时保存到项目根下的 `.data/logs/dev/`：

| 文件 | 内容 |
|---|---|
| `dev.log` | 启动、迁移、前后端合并输出 |
| `api.log` | API、Agent、写手调用异常和预览阶段记录 |
| `web.log` | Next.js 编译、代理与服务端错误（不含浏览器 console） |

每个文件到 10 MiB 轮转，保留 3 份，每行带时间戳，已去掉颜色码。`JC_DEV_LOG_DIR` 可改目录。日志里可能带第三方异常输出，不要不检查就上传。

```bash
tail -n 150 .data/logs/dev/api.log
grep 'preview_\|Traceback' .data/logs/dev/api.log
```

## 已删除的脚本

下面这些已经删掉，代码都还在 git 历史里，需要时取回，例如：

```bash
git show 6ad4632:myproject/job-come/scripts/verify_export_gate.py > /tmp/verify_export_gate.py
git checkout 6ad4632 -- myproject/job-come/scripts/      # 或者整个目录取回
```

| 类别 | 脚本 |
|---|---|
| 真实服务联调 | `test-live.sh`、`e2e_smoke.sh`、`agent_e2e.sh`、`regression_smoke.sh`、`v1_acceptance.sh` |
| 浏览器界面验收 | `verify_ui.py`、`verify_resume_steps.py`、`verify_agent_rail.py`、`verify_agent_reply.py`、`verify_agent_photo.py`、`verify_photo_crop.py`、`verify_confirmed_preview.py`、`verify_export_gate.py`、`verify_auth_errors.py`、`audit_visual.py` |
| 离线/契约检查 | `verify_error_copy.py`（含 `lib/error-copy-checks.mjs`）、`verify_intake_flow.py`、`evaluate_documents.py`、`evaluate_docling.py`、`check-export-agent.sh` |
| 真实模型/真实环境 | `evaluate_writing.py`（写作语义验收，调用真实模型）、`verify_export_regression.py`、`verify_concurrency_resilience.py`、`verify_exports.py`、`diagnose_stream.py` |
| 其它 | `calibrate_resume_pages.py`（重新测量页数预算）、`seed_demo.py`（演示账号） |

`docs/` 里仍有些文档提到它们，比如 `QA-TESTING.md` 和 `TECH-RESUME-WRITING.md`。那些描述的是当时的验收做法，不代表现在还能运行。
