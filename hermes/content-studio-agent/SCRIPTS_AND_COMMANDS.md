# 脚本与 CLI 命令

## 1. 主编排器：`content-studio.sh`

**路径**：`$HERMES_HOME/scripts/content-studio.sh`  
**环境**：`export HERMES_HOME=~/.hermes/profiles/content-studio`

### 1.1 命令表

| 命令 | 说明 |
|------|------|
| `daily [DATE]` | 日报；完成后可自动触发 video-pipeline |
| `radar [DATE]` | 工具雷达 |
| `weekly [DATE]` | 周报 |
| `video [DATE]` | 仅趋势视频脚本 + 分镜输入 |
| `video-pipeline [DATE]` | SOP 全链路：脚本 → GitHub 证据视频 → 发布包 |
| `video-render [DATE]` | 复用已有脚本，只重渲染 SOP 视频 |
| `video-mpt [DATE]` | 用已有脚本走 MoneyPrinterTurbo |
| `video-mpt-pipeline [DATE]` | 脚本 + MPT 全链路 |
| `video-mpt-bg [DATE]` | 后台 MPT（写 `logs/mpt-render-DATE.log`） |
| `video-mpt-resume [DATE]` | 从 sidecar 续轮询 MPT |
| `mpt-finish [DATE]` | 超时后标准收尾 |
| `mpt-status [DATE]` | MPT 进度与 sidecar |
| `video-hybrid [DATE]` | 已有脚本 → Hybrid 渲染 |
| `video-hybrid-pipeline [DATE]` | Hybrid 全链路 |
| `hybrid-status [DATE]` | Hybrid spec / 资产 / mp4 状态 |
| `community-pulse [DATE]` | 社区脉搏简报 |
| `library` | 刷新报告库索引 + Open Notebook 同步 |
| `notebook-sync` | 同步 reports → Open Notebook |
| `notebook-query` | 查询 Notebook 知识库 |
| `browse` / `stop-browse` | 本地浏览报告库 |
| `sop` / `rerun` / `full` / `all [DATE]` | 日常 SOP 全套 |
| `sop-status` / `status [DATE]` | 进度与产出文件清单 |
| `help` | 命令帮助 |

### 1.2 典型产物（`reports/YYYY/MM/`）

| 文件模式 | 含义 |
|----------|------|
| `YYYY-MM-DD.md` | 日报 |
| `YYYY-MM-DD-weekly.md` | 周报 |
| `YYYY-MM-DD-video-script.md` | 口播稿 |
| `YYYY-MM-DD-storyboard.md` | 分镜 |
| `YYYY-MM-DD-production-spec.yaml` | 制作规格 |
| `YYYY-MM-DD-video.mp4` | SOP 视频 |
| `YYYY-MM-DD-mpt-video.mp4` | MPT 视频 |
| `YYYY-MM-DD-hybrid-*.md/yaml/mp4` | Hybrid 链路 |

### 1.3 薄包装脚本

与 Cron 兼容的入口（内部调用 `content-studio.sh`）：

- `content-studio-daily.sh`
- `content-studio-weekly.sh`
- `content-studio-radar.sh`
- `content-studio-video-pipeline.sh`
- `content-studio-community-pulse.sh`
- `content-studio-web-story.sh`
- `setup-cron.sh`

---

## 2. `bundle/ops/scripts/`（全栈联调，可分享副本）

与 `hermes-dev/scripts/` 中 Content Studio 相关脚本一致；**分享时用 bundle 内副本**。

路径：`docs/hermes/content-studio-agent/bundle/ops/scripts/`

## 2b. `hermes-dev/scripts/`（monorepo 原件）

| 脚本 | 作用 |
|------|------|
| `sync-content-studio-secrets.sh` | 将 `secrets.env` 同步到 Notebook/MPT/OpenInspector 等 |
| `sync-notebook-llm-credentials.py` | Notebook LLM 凭证对齐 |
| `sync-mpt-llm-config.py` | MPT LLM 配置对齐 |
| `audit-llm-config.sh` | 审计各服务 base_url / key |
| `ali-tts-proxy.py` / `volcano-tts-proxy.py` | TTS 代理 |
| `verify-ali-tts-proxy.sh` | TTS 代理探活 |
| `content_studio_podcast_bootstrap.py` | Open Notebook 播客相关引导 |
| `fix-notebook-podcast-zh.py` | 播客中文修复 |
| `fix-notebook-speaker-voices.py` | 说话人音色 |
| `notebook-queue-maintain.py` | Notebook 队列维护 |
| `github_trending_snapshot.py` | 趋势快照（与 profile 内脚本同源逻辑） |
| `github-reports-browse.sh` | 浏览报告 |

栈入口：

- `hermes-dev/start-content-studio-stack.sh`
- `hermes-dev/stop-content-studio-stack.sh`

---

## 3. GitHub Analyst 基线脚本（git 内）

路径：`hermes-dev/profiles/github/scripts/`

| 脚本 | 说明 |
|------|------|
| `github-analyst.sh` | 主编排（对应早期 `content-studio.sh` 子集） |
| `github-analyst-daily.sh` | 日报 |
| `github-analyst-weekly.sh` | 周报 |
| `github-analyst-video-pipeline.sh` | 视频 pipeline |
| `generate_daily_report.py` | 日报生成 |
| `video_generator.py` | 视频渲染（skill 内亦有副本） |
| `setup-cron.sh` | Cron 安装 |

---

## 4. Agent 如何调用

在 Hermes 对话中应使用 **绝对路径 + 引号**：

```bash
"$HERMES_HOME/scripts/content-studio.sh" sop-status 2026-06-13
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline 2026-06-13
```

进度解析：grep `CONTENT_STUDIO_PROGRESS` in `$HERMES_HOME/logs/sop-latest.log`。
