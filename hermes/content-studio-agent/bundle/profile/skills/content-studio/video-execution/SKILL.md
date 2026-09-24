---
name: video-execution
description: "Hermes 视频生产执行手册：Chat 说「生成 sop视频 / 生成 mpt视频 / 生成 hybrid视频」时必须读此 Skill，用 terminal 跑 content-studio.sh，分阶段汇报进度与产出路径。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [视频, terminal, SOP, 执行, 进度]
    related_skills: [playbook, video-pipeline, moneyprinter-video, hybrid-video, video-script-generator]
---

# 视频生产执行手册（Hermes 必读）

当用户在 Chat 里说 **「生成 sop视频」**、**「生成 mpt视频」**、**「生成 hybrid视频」**，或 playbook 路由到视频 Pipeline / MPT / Hybrid 流程时，**必须先读本 Skill**，再按步骤执行。

本 Skill 把 Cursor Agent 手动跑通的流程固化为 Hermes 可复现的 terminal 执行 SOP。

## Hard Rules（违反即失败）

1. **必须用 `terminal` 工具**执行下方绝对路径命令。禁止只用 `read_file` / `write_file` 假装「已在渲染」。
2. **禁止 `execute_code` 跑视频 pipeline**（见 [工具白名单与黑名单](#工具白名单与黑名单)）。
3. **禁止口头敷衍**：未看到 terminal 退出码和 stdout 中的 `✅ Stage` / `CONTENT_STUDIO_PROGRESS` 行之前，不得对用户说「视频已生成」。
4. **长任务要告知预期**：sop 视频 Stage 2 通常 2–8 分钟；mpt 视频 Stage 2 通常 5–20 分钟（MPT API 轮询，可能需 resume）。
5. **每阶段结束后必须向用户汇报**（见 [Progress Report Template](#progress-report-template)）。
6. **失败时必须贴出 terminal 最后 30 行**，并给出排查表中的下一步，不得静默结束。
7. **三条链路互不替代**：sop、mpt、hybrid 产物独立命名，不得相互覆盖。
8. **禁止把执行责任推给用户**（见 [禁止对用户说的话](#禁止对用户说的话)）。

## 工具白名单与黑名单

视频生产（sop / mpt / hybrid）**只允许**下表「允许」列中的工具。选错工具 = SOP 失败，不是「变通方案」。

| 步骤 | ✅ 允许 | ❌ 禁止 | 禁止原因 |
|------|---------|---------|----------|
| 跑 `content-studio.sh video-*` | **`terminal`**（首选） | `execute_code` | 默认 300s 杀进程；stdout 50KB 截断；子进程易被 SIGKILL |
| 同上（Gateway 可能先断开） | **`terminal`** + `background=true`, `notify_on_complete=true` | 让用户「自己去终端粘贴」 | Agent 仍有责任启动任务并轮询状态 |
| 同上（MPT 常超过 10 分钟） | **`terminal`** → `video-mpt-bg` 或拆 Stage | `cronjob` 临时救火 | cron 异步、无即时 Progress Report；仅用于**已配置**的定时 SOP |
| 查进度 / 是否已有 mp4 | **`terminal`** → `sop-status` / `mpt-status` / `hybrid-status` | 凭记忆描述进度 | 用户看不到 shell stdout |
| 读 Skill / 脚本 / 产出 | `read_file`, `search_files` | 代替 terminal 执行 | 读文件不等于渲染 |
| 写脚本（Stage 1 失败降级） | `write_file` + 再 **`terminal` 渲染** | 只 write 不 terminal | 无 mp4 |
| 委托子 Agent | `delegate_task`（toolsets 含 **terminal**） | 子 Agent 只用 `execute_code` | 同上 timeout |

### 决策流程（每次视频请求必走）

```text
用户要 sop/mpt/hybrid 视频？
  ├─ 否 → 走 playbook 其他路由
  └─ 是 → 读 video-execution（本 Skill）
         → Preflight（一条 terminal）
         → 选命令：
              sop   → video-pipeline [DATE]
              mpt   → video-mpt-pipeline [DATE]  （脚本已有且只重渲染 → video-mpt）
              hybrid→ video-hybrid-pipeline [DATE]
         → 预期 >10 分钟 或 上次 MPT 超时？
              是 → video-mpt-bg [DATE]  或  terminal background+notify
         → 执行后验证 ls / *-status
         → Progress Report
```

### 禁止对用户说的话

以下话术表示 **Agent 选错工具或偷懒**，**一律禁止**（即使 terminal 曾失败也不得降级成这些）：

```text
❌ 「我无法直接调用 terminal / Shell」
❌ 「请你在命令行终端中粘贴并执行……」
❌ 「你可以用 execute_code 触发自动化脚本」
❌ 「建议通过 cronjob 来生成视频」（除非用户在配置定时任务）
❌ 「系统不允许我执行危险命令」（本 profile approvals.mode=off，WORKSPACE_AUTO_APPROVE=1）
```

**正确说法示例：**

```text
✅ 「我将用 terminal 执行 video-mpt-pipeline 2026-06-14，预计 5–20 分钟。」
✅ 「MPT 渲染已放后台，task 已写入 sidecar；我用 mpt-status 轮询。」
✅ 「Stage 2 超时但 task_id 仍在；执行 video-mpt-resume 继续轮询。」
```

### 为何不能用 execute_code（机制说明）

| 限制 | 值 | 后果 |
|------|-----|------|
| 默认 timeout | 300s | 到点 SIGKILL，MPT 渲染中途被杀 |
| stdout 上限 | 50 KB | Stage 2 长日志被截断 |
| 适用场景 | 短脚本、RPC | **不**适合 `content-studio.sh video-*` |

profile 虽把 `code_execution.timeout` 提到 1800，**仍禁止**用于视频——日志截断与误用风险不变。

## 禁止 execute_code 跑 pipeline

`execute_code` 资源限制（profile 已把 timeout 提到 1800，但**仍禁止**用于视频）：

| 限制 | 值 | 后果 |
|------|-----|------|
| 默认 timeout | 300s（全局默认；本 profile 已改 1800 作兜底） | 到点 SIGKILL，MPT 渲染中途被杀 |
| stdout | 50 KB | Stage 2 长日志被截断，你看不到进度 |
| 适用场景 | 短脚本、RPC 调工具 | **不**适合 `content-studio.sh video-*` |

**正确：直接 `terminal`**（不要包在 Python 里，不要 `subprocess.run` 写在 execute_code 里）：

```text
terminal(
  command="/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-pipeline 2026-06-13"
)
```

- **不要**传 `timeout=1800`（foreground 显式上限 600s 会报错）。
- **省略** timeout 参数 → 使用本 profile `terminal.timeout=3600`，命令跑完即返回。
- 若 gateway 可能先超时，用后台 + 通知：

```text
terminal(
  command="/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-pipeline 2026-06-13",
  background=true,
  notify_on_complete=true
)
```

完成后执行 `sop-status` 验证 mp4，再发 Progress Report。

**【特殊兜底：无 terminal 环境】**
如果遇到当前会话受限（`Tool 'terminal' does not exist`），被迫只能使用 `execute_code` 执行长任务时，**绝对禁止**使用 `subprocess.run` 阻塞等待（必定触发 1800s 超时被强杀，导致渲染中断）。
必须使用 `subprocess.Popen` 异步放入后台，脱离 Python 生命周期，后续使用 `*-status` 进行轮询：
```python
import subprocess
cmd = ["/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh", "video-pipeline", "2026-06-13"]
subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
print("任务已异步放入后台，稍后请使用 sop-status 轮询进度")
```

## Three Pipelines

| 用户说法 | 命令 | 成片 | 画面特点 |
|----------|------|------|----------|
| 生成 **sop视频** / sop视频 / 主视频 / GitHub 滚动视频 | `video-pipeline` | `*-video.mp4` | 日榜图 + 项目介绍卡 + **GitHub 页面滚动红框** |
| 生成 **mpt视频** / mpt视频 / MPT 视频 / 素材混剪 | 见下方 **MPT 命令二选一** | `*-mpt-video.mp4` | **Pixabay 通用 B-roll** + 口播字幕；**不会出现 GitHub 页面** |
| 生成 **hybrid视频** / AI增强视频 / 相关素材视频 | `video-hybrid-pipeline` | `*-hybrid-video.mp4` | 第三条独立链路：概念卡 + GitHub 证据占位/后续滚动 + Seedance/fallback AI 素材 |

**MPT 命令二选一（单次 terminal，禁止叠加 sop pipeline）**

| 条件 | 唯一命令 | 禁止 |
|------|----------|------|
| `*-video-script.md` 已存在 | `video-mpt [DATE]` | `video-pipeline`、`video-mpt-pipeline`（除非用户要重生成脚本） |
| 无脚本 / 需从日报生成脚本 | `video-mpt-pipeline [DATE]` | `video-pipeline`、同时再跑 `video-mpt` |

**反模式（禁止）**：用户说「生成 mpt 视频」时执行 `video-pipeline` + `video-mpt`，或向用户介绍「两条分支都要跑」。mpt 请求 **只走 MPT 一条链**。

**常见误解**：MPT 成片「口播在讲 GitHub 项目，画面却是 coding/程序员素材」——这是设计如此。MPT 只读口播文本做 TTS + 素材搜索，不会打开 GitHub。若要项目画面对应，必须走 **sop视频 / video-pipeline**（且用户必须明确要 sop，不是 mpt）。

**脚本不一致**：若 `*-video-script.md` 是后来重写的，但 MPT 用的是 Cron 降级脚本生成的旧版，成片口播会与当前脚本不符。渲染前执行：

```bash
ls -lh /Users/gqli/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD-video-script.md
```

若用户要求「用最新脚本重跑 MPT」，先确认脚本 mtime，再跑 `video-mpt`。

## Command Map

`HERMES_HOME` 固定为 `/Users/gqli/.hermes/profiles/content-studio`。

```bash
# 主视频（SOP 视频链路，不含完整日报 SOP）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-pipeline
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-pipeline 2026-06-13

# MPT 视频（脚本 + 素材混剪完整链路）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-pipeline
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-pipeline 2026-06-13

# Hybrid 视频（相关素材 + 概念卡 + Seedance/fallback）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-hybrid-pipeline
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-hybrid-pipeline 2026-06-13

# 已有脚本，仅重渲染
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-render 2026-06-13   # SOP
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt 2026-06-13        # MPT

# 查最近一次 pipeline 进度（无需重跑）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh sop-status
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh sop-status 2026-06-13
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh hybrid-status 2026-06-13
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh mpt-status 2026-06-13

# MPT 长任务：后台渲染（Hermes 不必阻塞等待）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-bg 2026-06-13

# MPT 轮询超时后：用 sidecar 中的 task_id 续跑（不重新提交任务）
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt-resume 2026-06-13
```

用户说 **「重跑 SOP」** / **「sop」** / **「full」** 时走完整日常 SOP（日报→雷达→社区→视频→报告库），不是本 Skill 的「sop视频」：

```bash
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh sop
```

## Preflight（执行 terminal 之前）

向用户简要说明将要跑哪条链路，然后 **一条 terminal 命令** 做前置检查：

```bash
DATE="${DATE:-$(date +%Y-%m-%d)}"
Y="${DATE:0:4}"; M="${DATE:5:2}"
BASE="/Users/gqli/.hermes/profiles/content-studio"
echo "=== Preflight $DATE ==="
test -f "$BASE/reports/$Y/$M/$DATE.md" && echo "OK daily" || echo "MISSING daily — video-pipeline 会失败"
curl -sf -o /dev/null -w "MPT HTTP %{http_code}\n" http://127.0.0.1:8082/docs || echo "MPT down — mpt 链路会失败"
/Users/gqli/work/deepagents/venv/bin/python3 -c "import playwright" 2>/dev/null && echo "OK playwright" || echo "MISSING playwright — sop 渲染会失败"
```

- 跑 **sop视频** 且日报不存在：先问用户是否补跑 `daily $DATE`，或指定有日报的日期。
- 跑 **mpt视频** 且 MPT 不可达：告知启动栈 `cd /Users/gqli/work/deepagents/hermes-dev && ./start-content-studio-stack.sh`，或只启动 MPT。

## Execution SOP — 生成 sop视频

```
Step 0 — 读 playbook [五b] + video-pipeline Skill（了解 Stage 定义）
Step 1 — Preflight
Step 2 — terminal 执行 video-pipeline [DATE]（省略 timeout 或 background+notify；**禁止 execute_code**）
Step 3 — 解析 stdout 中的 CONTENT_STUDIO_PROGRESS / ✅ Stage 行
Step 4 — 验证产出:
         ls -lh reports/YYYY/MM/YYYY-MM-DD-video.mp4
         ls -lh reports/YYYY/MM/YYYY-MM-DD-video-script.md
Step 5 — Progress Report Template 回复用户
Step 6 — 失败 → Failure Playbook
```

**Stage 含义（video-pipeline）**

| Stage | 产出 | 典型耗时 |
|-------|------|----------|
| 1 | `*-video-script.md` | 1–3 min（Hermes 子会话写脚本） |
| 2 | `*-video.mp4` | 2–8 min（TTS + Playwright + ffmpeg） |
| 3 | `*-video-publish.md` + Web Story | < 1 min |

## Execution SOP — 生成 mpt视频

```
Step 0 — 读 moneyprinter-video Skill + 向用户说明「画面为通用素材，非 GitHub 页面」
Step 1 — Preflight（MPT 8082 + 日报存在）；**禁止** video-pipeline
Step 1b — ls -lh *-video-script.md：有脚本 → 本 SOP 只用 video-mpt；无脚本 → 只用 video-mpt-pipeline
Step 2 — 选执行方式（**禁止 execute_code**；**本轮只提交一条 MPT 命令**）:
         A) 有脚本: terminal → video-mpt [DATE]（或易超时 → video-mpt-bg）
         B) 无脚本: terminal → video-mpt-pipeline [DATE]（或易超时 → 先 pipeline 完成脚本后再 video-mpt-bg，分两轮）
         C) Gateway 易断: terminal background=true, notify_on_complete=true
Step 3 — 每 3–5 分钟 terminal → mpt-status [DATE]（或 sop-status），把进度贴回 Chat
Step 4 — 若 Stage 2 超时 / Gateway 断开 / 有 sidecar 无 mp4 / 有 mp4 无 *-mpt-video-publish.md：
         **必须** terminal → mpt-finish [DATE]（自动 resume + 补发布包）
Step 5 — 验证产出 + Progress Report（必须含 mp4 + publish.md + cover.jpg）
Step 6 — 失败 → Failure Playbook
```

## 长任务与超时策略（超时本身解决不了时）

**原则**：不要把「等一条命令跑完」绑死在单轮 Chat / 单次 foreground terminal 上。

| 策略 | 命令 | 适用 |
|------|------|------|
| 提高 MPT 轮询上限 | `MONEYPRINTER_TIMEOUT=1800 content-studio.sh video-mpt DATE` | 服务慢但最终会完成 |
| 后台渲染 | `video-mpt-bg DATE` | Hermes/Gateway 先超时，但本机 MPT 继续跑 |
| 标准收尾 | `mpt-finish DATE` | **超时/断线后必跑**：续轮询 + 补封面/发布指引 |
| 断点续轮询 | `video-mpt-resume DATE` | mpt-finish 仍缺 mp4 时再用 |
| 拆 Stage | 先 `video DATE`（脚本），再 `video-mpt DATE`（只渲染） | Stage 1 失败可单独重试 |
| 状态查询 | `mpt-status DATE` | 任意时刻查 mp4 / sidecar / 后台日志 |
| Agent 后台 terminal | `background=true`, `notify_on_complete=true` | 与 video-mpt-bg 二选一 |

**MPT 超时后的标准动作（必须按序）：**

```text
1. terminal → mpt-status DATE
2. terminal → mpt-finish DATE          # 必跑：resume + 发布包
3. 仍无 mp4 → video-mpt-resume DATE
4. 仍失败 → 贴 logs/mpt-render-DATE.log 末尾 + MPT 服务日志
```

**Stage 含义（video-mpt-pipeline）**

| Stage | 产出 | 典型耗时 |
|-------|------|----------|
| 1 | `*-video-script.md` | 1–3 min |
| 2 | `*-mpt-video.mp4` | 5–15 min |
| 3 | `*-mpt-video-publish.md` + cover | < 1 min |

## Execution SOP — 生成 hybrid视频

```
Step 0 — 读 hybrid-video Skill，确认这是第三条独立链路
Step 1 — terminal 执行 video-hybrid-pipeline [DATE]（省略 timeout 或 background+notify；禁止 execute_code）
Step 2 — 验证产出:
         *-hybrid-storyboard.md
         *-hybrid-production-spec.yaml
         assets/YYYY-MM-DD-hybrid/
         *-hybrid-video.mp4（v1 可为静音概念卡合成视频）
Step 3 — terminal 执行 hybrid-status [DATE]
Step 4 — Progress Report 回复用户，说明 sop/mpt 未被覆盖
```

**Stage 含义（video-hybrid-pipeline）**

| Stage | 产出 | 典型耗时 |
|-------|------|----------|
| 1 | `*-hybrid-production-spec.yaml` | < 1 min |
| 2 | `assets/*-hybrid/` | 1-5 min（Seedance 未配置时 fallback 更快） |
| 3 | `*-hybrid-video.mp4` | < 2 min（v1 卡片合成） |
| 4 | `*-hybrid-video-publish.md` | < 1 min |

## Progress Report Template

terminal 结束后，**必须**用如下结构回复（填真实路径与 ls 结果）：

```markdown
## 视频生产进度 — {DATE} — {sop|mpt}

| 阶段 | 状态 | 产出 |
|------|------|------|
| Preflight | ✅/❌ | 日报 / MPT / Playwright |
| Stage 1 脚本 | ✅/❌ | `...-video-script.md` ({size}) |
| Stage 2 渲染 | ✅/❌ | `...-video.mp4` 或 `...-mpt-video.mp4` ({size}) |
| Stage 3 发布包 | ✅/❌ | publish.md / cover |

**预览**: `open "绝对路径"`  
**说明**: {mpt 需加一句「画面为素材混剪，项目介绍请看 sop 视频」}
```

若命令仍在跑（长任务），至少每 3 分钟更新一次：

```markdown
⏳ Stage 2 渲染中… 已运行 {N} 分钟。最新日志: `content-studio.sh sop-status {DATE}`
```

## Failure Playbook

| 现象 | 原因 | 动作 |
|------|------|------|
| `GitHub 页面滚动方案未成功` | 网络 / Playwright | `curl -I https://github.com`；重装 Chromium；重跑 `video-render` |
| `MoneyPrinterTurbo 未启动` | 8082 未监听 | 启动 content-studio 栈 |
| MPT 任务 state=-1 | Pixabay 素材 / TTS | 查 MPT 日志；确认 `video_source: pixabay` |
| `MoneyPrinterTurbo 超时（600s）` | 轮询上限到点，任务可能仍在 MPT 内跑 | **`mpt-status` → `video-mpt-resume`**；勿重新 POST |
| Gateway/Chat 先断开 | foreground terminal 太长 | 下次用 **`video-mpt-bg`** 或 background+notify |
| Stage 1 降级脚本 | Hermes 子会话超时 | 读脚本是否泛化 TOP5；用 Chat 重写脚本后再 `video-mpt` |
| `execute_code` 300s timeout | 误用 execute_code 跑 pipeline | **改用 terminal**；见 video-execution「禁止 execute_code」 |
| `Script timed out after 300s` | 同上 | 重启 gateway 后重试；config 已设 code_execution.timeout=1800 作兜底，但仍必须用 terminal |
| 有 mp4 但口播不对 | 旧脚本 | 确认 script mtime → 重跑 `video-mpt DATE` |

## Workspace UI 反馈弱 — Hermes 侧补救

Workspace 长 terminal 输出常折叠在 tool 结果里，用户看不到分阶段卡片。Hermes **必须**：

1. 跑命令前发一条「开始 Stage X，预计 N 分钟」。
2. 命令结束后发 [Progress Report Template](#progress-report-template)，不要只总结「完成了」。
3. 用户问进度时跑 `content-studio.sh sop-status [DATE]`，把摘要贴回 Chat。
4. 禁止在未执行 terminal 时描述渲染进度。

## Related

- `video-script-generator` — 脚本须含 **项目深描**（公众号式深度介绍 + 保留 thesis 开场），见 `references/wechat-style-project-intro.md`
- `video-pipeline` — GitHub 滚动渲染细节
- `moneyprinter-video` — MPT API 与产物命名
