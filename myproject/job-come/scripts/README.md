# JC Scripts

> **日常开发只需要两个入口：** `./scripts/dev.sh` 启动本地服务，`./scripts/test-local.sh` 运行不依赖真实外部服务的本地检查。

## 常用入口

| 命令 | 何时使用 | 是否需要真实外部依赖 |
|---|---|---|
| `./scripts/setup-venv.sh` | 首次准备开发环境或依赖变更后 | 需要本机 Python/包安装 |
| `./scripts/dev.sh` | 启动本地 API、Web 和内嵌 Agent | MySQL/Redis/LLM/TOS 按 `.env` 配置 |
| `./scripts/test-local.sh` | 提交前、本地回归、候选版本代码检查 | 否；不会调用真实 API/Agent/TOS/邮件 |
| `./scripts/test-live.sh smoke` | 本地或 staging 的核心 API + PDF/DOCX 导出联调 | 是，需 API、账号及相关服务 |
| `./scripts/test-live.sh agent` | Agent/DeerFlow、SSE、消息持久化、取消联调 | 是 |
| `./scripts/test-live.sh regression` | 回归样本的简历、JD、双语预览联调 | 是 |
| `./scripts/v1_acceptance.sh` | V1 上线前四项真机验收的统一入口（见下方「真实服务联调」） | 是，且需要生产构建 Web |
| `./scripts/db_upgrade.sh` | 明确执行数据库 migration | MySQL |
| `./scripts/seed_demo.py` | 创建本地演示账号/数据 | MySQL/Redis |
| `./scripts/prune_llm_log.py` | 按留存窗口清理 LLM 调用审计日志（生产 cron） | MySQL |

## 本地运行日志（自动保存）

使用 `./scripts/dev.sh` 启动后，终端输出同时保存到项目根下：

| 文件 | 内容 |
|---|---|
| `.data/logs/dev/dev.log` | 启动、迁移、前后端合并输出 |
| `.data/logs/dev/api.log` | API、Agent、写手调用异常和预览阶段记录 |
| `.data/logs/dev/web.log` | Next.js 编译、代理与服务端错误（不包含浏览器 console） |

路径固定，重启追加；每个文件到 10 MiB 后自动轮转，保留 3 份备份（`.1`～`.3`），
三个日志合计约最多 120 MiB。每行添加本机时间和时区偏移，落盘移除 ANSI 颜色码。
默认目录已被 `.data/` 的 Git ignore 规则覆盖，日志文件权限仅当前用户可读写。
可在启动前设置 `JC_DEV_LOG_DIR` 覆盖目录。

```bash
tail -n 150 .data/logs/dev/api.log
tail -f .data/logs/dev/dev.log
grep 'preview_\|Preview\|Traceback' .data/logs/dev/api.log
```

预览新增 `preview_preflight_started/completed` 和 `preview_lifecycle` 记录。
后者包含本次 `run_id`、profile ID、阶段、耗时、成功/失败以及每 10 秒一次的等待记录，
可区分卡在流开始前、档案读取、写作、保存、渲染还是检查。
不额外记录简历正文、prompt、响应正文或 Cookie；但现有第三方异常输出可能包含敏感信息，
日志仅供本地诊断，不要未经检查公开上传。

这只是开发运行日志，不代替数据库中的 session/message/trace，也不用于多实例业务持久化。
日志从下次使用新脚本启动时开始捕获，无法补回之前只输出到终端的历史日志。
前端浏览器中的 JS 错误和 Network 信息仍需浏览器提供，`web.log` 不会自动采集它们。

## 解释器与路径：自动纠正，不需要手动管理

所有 `scripts/*.py`（除 `evaluate_docling.py`，见下）第一行可执行代码都是：

```python
from lib.bootstrap import ensure_project_env
ensure_project_env()
```

不管用 `python scripts/x.py`、裸 `./scripts/x.py`、还是从任意目录调用，这一行都会：

1. 找到 monorepo 根目录（同时拥有 `venv/bin/python` 和 `libs/agentkit` 的那一层），不依赖脚本
   自己在哪一层目录，也不是硬编码 `parents[N]`。
2. 如果当前解释器不是项目 `venv` 里的那个 `python`（比如解析到了 pyenv shim、系统 Python、
   别的 venv），**原地 `os.execv` 重新执行自己**换到正确的解释器，`sys.argv` 原样保留，
   对调用方透明。
3. 把 `backend/server/src` 加进 `sys.path`，所以 `import jc...` 不依赖调用时的 cwd。

这解决的是一类真实出现过的故障：裸 `python scripts/x.py` 解析到没装 `pymupdf`/`markitdown`
的解释器，PDF 解析在那个环境里直接退化成"读不出内容"，报错看起来像是文档本身有问题，
实际上纯粹是解释器选错了。`JC_PYTHON` 环境变量可以显式指定目标解释器覆盖自动检测，
语义和 `dev.sh` 的 `JC_PYTHON` 一致。

**唯一的例外是 `evaluate_docling.py`**：它故意运行在用 `--docling-source` 指定的独立环境里
（装了 Docling 重型依赖，不是 JC 自己的 `venv`），所以没有加这段自举逻辑——加了反而会把它
错误地拉回没有 `docling` 的 JC 环境。

## 本地开发推荐流程

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/setup-venv.sh                # 首次或依赖变更时
cp backend/server/.env.example backend/server/.env  # 首次时
./scripts/dev.sh                        # 终端 1：启动 API + Web
./scripts/test-local.sh                 # 终端 2：代码、测试、构建检查
```

`dev.sh` 默认启动 Web `http://127.0.0.1:3000`、API `http://127.0.0.1:8000/api/v1`。DeerFlow Agent 内嵌在 API Python 进程内，不需要单独启动第三个 Agent 服务。

## 按职责分类

### 运行与部署

- `dev.sh`：开发启动入口。
- `db_upgrade.sh`：在 `backend/server/` 执行 Alembic migration（使用同目录 `alembic.ini`）。
- `install-production.sh`：以锁定依赖安装生产运行时。
- `prune_llm_log.py`：对 `jc_llm_call` / `jc_llm_call_attempt` 执行留存清理。审计表里存着 prompt 与
  模型响应全文，对 JC 来说就是简历正文，所以它**必须有人定期删**。默认 dry-run 只报数，
  `--apply` 才真删；`--forget-payload-after N` 是中间档——只清三列正文、保留指标与失败码，
  适合「成本与可靠性历史比内容更值钱」的时候。留存天数默认取 `JC_LLM_LOG_RETENTION_DAYS`（90）。
  表结构与开关见 `docs/architecture/TECH-LLM.md` §4.1。
- `sync-deerflow-upstream.sh`：**维护动作**，同步 vendored DeerFlow；不是日常开发或生产部署步骤。
- `lib/project_paths.sh`：供 shell 脚本 `source` 的路径工具，不直接执行。
- `lib/error-copy-checks.mjs`：`verify_error_copy.py` 运行的断言体，由它编译后注入，不直接执行。

### 本地质量检查

- `test-local.sh`：Python 全量测试、前端生产构建、文档评测输出、建档走查、脚本语法检查；可选 UI 验收开关。
- `verify_intake_flow.py`：**离线**建档全链路走查，已接入 `test-local.sh`，不需要浏览器/模型/MySQL。
  用同一份档案跑两遍完整访谈——一遍走 `IntakeService`（面板），一遍走 `jc_intake_plan` /
  `jc_intake_record`（舟卡聊天）——断言两者都到达 `can_generate` 且**主经历真被填满**。
  守的是两个静默故障：问题 id 重编号导致访谈永远差一条；答案只存成证据、没写进结构化字段。
  输出 `docs/evidence/intake-flow.json`。理由见 `docs/operations/QA-TESTING.md`「建档走查」。
- `verify_ui.py`：独立 UI 夹具/浏览器验收，`test-local.sh` 中以 `RUN_UI_ACCEPTANCE=1` 显式启用。
- `audit_visual.py`：真实浏览器里的机械视觉审计（对比度、失效 Tailwind class、横向溢出、字号标尺）。
  需要先起好前端生产构建，用 `--base` 指定地址；发现问题以非 0 退出。详见
  `docs/architecture/TECH-DESIGN-SYSTEM.md` 第 10 节。
- `verify_resume_steps.py`：简历第 1/3/4 步的真机验收 + 版面量化门禁（两列/堆叠两种模式各跑一次、
  左栏字号档数）。需要先起好前端生产构建，`--base` 指定地址。
- `verify_agent_reply.py`：真实浏览器 + 隔离 API 夹具，验证大块 token 与 done 同时到达时仍逐字输出、
  标题/编号/粗体、确认卡片不被折叠、点击确认后刷新档案、历史不重播；同时检查减少动态效果偏好。
  不调用真实模型或数据库。运行 `python scripts/verify_agent_reply.py --base http://127.0.0.1:3000`。
  渲染器纯测试：在 `frontend/web` 执行 `node --test tests/agent-rich-text.test.cjs`。
- `diagnose_stream.py`：可选真实 SSE 到达时间对照。**会创建测试账户/档案并调用模型（可能计费）**，
  直接 API 与前端代理分别采样，不能仅凭两次独立生成的时间差判定根因。
- `verify_agent_rail.py`：舟卡侧栏收起/展开闭环。核心是**收起不卸载**：在运行在途时收起，
  确认流式回复仍然到达。同上需要前端生产构建 + `--base`。
- `verify_export_gate.py`：第 4 步**导出永不被质检拦住**。三个 case：读到发现（看过即可下载）、
  没有结论（一开始就能下载，且不呈现为简历的问题）、请求一直不返回（可跳过等待，迟到结果不重新上锁）。
  同上需要前端生产构建 + `--base`。理由见 `docs/architecture/TECH-RESUME-WRITING.md` §6.3.1。
- `verify_error_copy.py`：失败时用户读到的文案。用项目自己的 TypeScript 编译 `lib/api/errors.ts`
  与 `lib/api/user-error.ts` 再跑断言（`lib/error-copy-checks.mjs`），**不需要浏览器、不需要起服务**，
  所以已接入 `test-local.sh`。守的是：请求没到达要说「没连上服务」而不是「请求失败」，
  服务端英文串不得出现在界面上。理由见 `docs/operations/QA-TESTING.md`「失败文案是发布门禁」。
- `verify_auth_errors.py`：同一批行为的真机版本——驱动登录页与忘记密码页，确认文案真的渲染出来，
  且重置邮件的成功与失败不共用一个提示框。需要先起好前端生产构建，`--base` 指定地址。
- `verify_exports.py`：导出物视觉/结构证据的专用检查工具。
- `evaluate_documents.py`：轻量文档解析质量评测，输出 `docs/evidence/document-evaluation.json`。
- `evaluate_docling.py`：使用本地 Docling 源码的隔离评测，不默认纳入常规本地测试。

### 真实服务联调

- `test-live.sh`：**唯一的用户入口**；用参数选择 `smoke`、`agent`、`regression` 或 `all`。
- `e2e_smoke.sh`、`agent_e2e.sh`、`regression_smoke.sh`：由 `test-live.sh` 调度的分项实现，通常无需直接运行。
- `v1_acceptance.sh`：**V1 上线前四项真机验收的统一入口**，沙箱环境做不到，需要本机或
  指定环境跑。依次跑：(1) 浏览器类验收（`verify_ui.py`/`audit_visual.py`/
  `verify_resume_steps.py`/`verify_agent_rail.py`/`verify_export_gate.py`/
  `verify_auth_errors.py`，需要先 `npm run build && npm start` 起生产构建）；
  (2) 打印文档解析的手动跑法提示（需要真实简历文件，不是合成样本，脚本本身不替你跑）；
  (3) `verify_export_regression.py`（导出全量回归：pdf/docx/html × zh-CN/en-US/zh-en 九种组合，
  真实下载 + 页数/字体/链接检查）；(4) `verify_concurrency_resilience.py`
  （并发隔离 + 取消 + 可选的重启恢复）。每项写一份 JSON 证据到 `docs/evidence/`，
  任一项失败整体以非 0 退出。先 `./scripts/dev.sh` 起好 API + Web，再设
  `JC_E2E_EMAIL`/`JC_E2E_PASSWORD`，跑 `./scripts/v1_acceptance.sh --help` 看全部参数。
- `verify_export_regression.py`：`v1_acceptance.sh` 第 3 项的实现，也可单独跑。
- `verify_concurrency_resilience.py`：`v1_acceptance.sh` 第 4 项的实现，也可单独跑；
  默认跳过重启步骤（它是脚本里唯一需要人工介入的环节——跑到提示时手动重启 API 进程、
  按回车继续），加 `--with-restart` 才会停下来等你重启。

## 已移除的重复脚本

- `ci_regression.sh`：仅重复 `test-local.sh` 中已有的测试子集。
- `export_smoke.sh`：其 PDF 导出验证已并入 `test-live.sh smoke`。

## 常用环境变量

```bash
# dev.sh
JC_SKIP_DB_UPGRADE=1
JC_API_RELOAD=false
JC_WEB_CLEAN=false

# test-live.sh
JC_E2E_BASE=http://127.0.0.1:8000/api/v1
JC_E2E_EMAIL=...
JC_E2E_PASSWORD=...

# test-local.sh 的可选额外门禁
RUN_UI_ACCEPTANCE=1 UI_BASE_URL=http://127.0.0.1:3107
```

真实凭据只写入本地 `backend/server/.env` 或密钥管理系统，绝不写入脚本、README 或 Git。

## 头像裁剪回归

`python scripts/verify_photo_crop.py`：先保持前端在 3000 端口运行。
使用全新的隔离浏览器和拦截的 API fixtures，不写真实数据库、不调用模型。
检查桌面 / 320px 窄屏的选区移动、四角等比调整、缩放、键盘操作，
并解析上传的 multipart JPEG，比对输出尺寸和选区像素、检查缩略图刷新。
浏览器截图保存在 `/tmp/jc-photo-selection-*.png` 和 `/tmp/jc-photo-crop-*.png`。
纯几何回归在前端目录运行 `node --test tests/image-crop.test.cjs`。

## Agent 设置头像回归

`python scripts/verify_agent_photo.py`（前端已在 3000 运行；可用 `UI_BASE_URL` 指定）：
隔离浏览器拦截所有 API，模拟 `jc_profile_photo_set` 的结构化工具结果，验证从聊天图片读取、
打开裁剪、取消不写入、默认不展示、确认保存仅上传一次以及刷新档案缩略图。
不访问真实数据库、不调用付费模型。此脚本验证 UI 集成，不替代真实模型的工具选择验收。

头像工具不新增表：图片来源复用会话附件的对象存储，最终照片复用档案头像上传接口。
工具仅接受当前会话的消息 ID / 附件序号，不接受 URL、对象存储 key 或客户端身份。
多图时需先向用户确认选图；裁剪和展示开关始终由用户在前端确认。

## 确认修改后的优化预览回归

`python scripts/verify_confirmed_preview.py`：前端已启动，默认 3000，可用 `UI_BASE_URL` 指定。
隔离浏览器 / 拦截所有 API，验证优化预览中收到路径型修改、点击确认后刷新档案版本，
重新读取预览并在原位置显示修改后的要点；不写真实数据库、不调用模型。

导出检查总预算默认 `JC_EXPORT_REVIEW_TIMEOUT_SECONDS=90` 秒（最大 120）。
Next API 代理等待 180 秒，避免默认 30 秒先断开；改动 Next 配置后需要重启前端。
预算耗尽返回 `unavailable / reviewed=false`，不是审核失败或通过，确定性检查仍保留。
本地代理回归（两个随机端口、31秒响应，无需项目服务）：
`cd frontend/web && RUN_PROXY_INTEGRATION=1 node --test tests/dev-proxy-timeout.test.mjs`。

## 无付费模型的导出与 Agent 专项回归

从项目根运行 `./scripts/check-export-agent.sh`：真实临时 SQLite、真实 PDF/Word/HTML
渲染及文件完整性检查、确认写入/拒绝/重试/版本冲突/权限、长 patch 短回执、断流后的
确认持久化、done 与回复提交顺序、全量 trace 与 UI 投影隔离。
不连真实业务数据库、不调用真实模型、不启动/停止服务。PDF 需要已安装的 Playwright Chromium。
真实模型是否按用户意图修改、MySQL 多 worker 并发与线上部署不在该脚本的保证范围。

本次新增 `015_agent_message_longtext` 迁移（仅加宽 `jc_agent_message` 两列，不新增表）。
项目根 `./scripts/db_upgrade.sh` 后自行重启后端。导出不再重复调用 reviewer；质检仍由
`export/review` 提供，导出保留已有结论而不冒充通过。详细自查及未完成风险见
`docs/evidence/2026-10-19-export-agent-audit.md`。
