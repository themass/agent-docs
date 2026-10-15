# Hermes Agent 版本演进（CalVer + Semver）

<!-- legacy-review:start -->
> **2026-10-15 校订导航**：历史版本怎样读，源码身份与安装版本怎样区分。\
> **核对范围**：旧未发版章节限定为 2026-07-22 快照；未联网重新核验发布矩阵。\
> **适用基线**：本地源码 `60d00c5633ad`；不是最新发布版本声明。原稿版本、行号、性能数字与长代码块若未在校订范围内，仍按历史示例阅读。
> **先读当前结论**：[当前实现导读](CURRENT_IMPLEMENTATION.md#current-evidence) · **现行分卷**：[09-reference-history-and-versions.md](../../volumes/09-reference-history-and-versions.md) · [具体改动与未验证项](REVIEW_AND_CHANGES.md) · [返回全目录](README.md)

<!-- legacy-review:end -->
<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 如何查版本](#section-1)
- [2. 版本矩阵（v0.10 → v0.19）](#section-2)
- [3. 历史未发版记录（相对 `v2026.7.20`，仅描述 2026-07-22 快照）](#section-3)
- [4. 工作区增量（2026.9.24 戳，文档 2026-10-14）](#section-4)
- [5. 更早版本（速览）](#section-5)
- [6. 按能力域归类（跨版本）](#section-6)
- [7. 读文档时的版本提示](#section-7)
<!-- visible-toc:end -->




> **当前发版 tag**: `0.19.0`（`v2026.7.20`）  
> **工作区 `hermes-dev/hermes-agent`**: `__release_date__` **2026.9.24**（`hermes_cli/__init__.py`）；可能领先 tag  
> **核对日期**: 2026-10-14 · 文档索引 [CATALOG.md](../../CATALOG.md)\
> **来源**: 签名 git tag 注解（`scripts/release.py` 发布）；仓库内 **无** 根级 `CHANGELOG.md`

---

<a id="如何查版本"></a>
<a id="section-1"></a>
## 1. 如何查版本

```bash
hermes version
# 或
python -c "from hermes_cli import __version__, __release_date__; print(__version__, __release_date__)"
git describe --tags   # 可能显示 v2026.7.20-NNN-g<sha>
```

**说明**：`main` 可能领先最新 tag；生产环境以 **已安装 wheel / tag** 为准。

---

<a id="版本矩阵v010-→-v019"></a>
<a id="section-2"></a>
## 2. 版本矩阵（v0.10 → v0.19）

| CalVer tag | Semver | 代号 / 主题 | 主要升级 |
|------------|--------|-------------|----------|
| **v2026.7.20** | **0.19.0** | The Connection Release | **Desktop SSH** 远程后端、**live subagent transcripts**、Claude Sonnet 5、session-scoped reasoning effort、`/model --once`、delivery-obligation ledger、Desktop Capabilities 大改（TTS/STT/terminal backend）、**api_content sidecar**（prompt cache 精确字节）、provider `enabled: false`、Kimi adaptive thinking、terminal billing（TUI `/topup`）、Desktop billing tab |
| v2026.7.7 / v2026.7.1 | 0.18.0 | The Bridge Release | **Raft** channel 向导、Vertex AI Gemini OAuth、Slack Block Kit 表格、MOA trace JSONL、**/debug** 诊断上传、PowerShell LSP、Kanban 通知路由、delegate 子 agent 继承父 toolsets |
| **v2026.6.19** | **0.17.0** | The Reach Release | iMessage（Photon）、**Raft** channel、**async subagents**、图像编辑、Cursor Composer（xAI Grok）、Dashboard profile builder、memory 工具升级、WhatsApp Business Cloud、Telegram 增强、Curator 成本优化 |
| v2026.6.5 | 0.16.0 | The Surface Release | **原生 Desktop**、浏览器管理面板、remote-gateway connect、桌面简中 UI、精简默认 skills、NVIDIA/skills 信任源、fuzzy `/model`、**`/undo`** |
| v2026.5.29 | 0.15.1 | Hotfix | Dashboard loopback 无限刷新修复；Kanban worker SIGTERM；`/model` 统一；`/yolo` session bypass；skills.sh 全目录；`.md` 媒体投递；gateway probe-stepdown；Kanban worker vision；Docker 加固 |
| v2026.5.28 | 0.15.0 | The Velocity Release | **`run_agent.py` 16k→3.8k LOC 重构**；Kanban → 多 Agent 平台；**session_search ~4500×**；promptware 防御；Bitwarden Secrets Manager；Krea + FAL plugin；Nous MCP 目录；OpenHands skill；**ntfy（第 23 平台）** |
| v2026.5.16 | 0.14.0 | The Foundation Release | **Windows 原生（早期 beta）**、**PyPI wheel**、冷启动优化、供应链加固、OAuth 本地 OpenAI 兼容代理、**跨 session Claude prompt cache**、LINE + SimpleX、Microsoft Graph、`/handoff`、`x_search`、`vision_analyze`、LSP diagnostics、`video_generate`、`computer_use` cua-driver |
| v2026.5.7 | 0.13.0 | The Tenacity Release | **Durable Kanban**、**`/goal`**、Checkpoints v2、gateway auto-resume、`no_agent` cron watchdog、post-write delta lint、**Google Chat（第 20 平台）**、**ProviderProfile** 可插拔、7 语言 i18n、`video_analyze` |
| v2026.4.30 | 0.12.0 | The Curator release | **后台 Curator + 自进化循环**；4 推理 provider；Teams + 元宝（18/19 平台）；Spotify + Google Meet；ComfyUI + TouchDesigner-MCP 默认捆绑；TUI 冷启动 ~57% 削减 |
| v2026.4.23 | 0.11.0 | The Interface release | **Ink TUI**、可插拔 transport、原生 AWS Bedrock、GPT-5.5（Codex OAuth）、QQBot（17 平台）、**Dashboard 插件系统** |
| v2026.4.16 | 0.10.0 | Tool Gateway release | Nous Portal 订阅：web search、图像生成、TTS、浏览器自动化 |

---

<a id="历史未发版记录相对-v2026720仅描述-2026-07-22-快照"></a>
<a id="section-3"></a>
## 3. 历史未发版记录（相对 `v2026.7.20`，仅描述 2026-07-22 快照）

以下在 tag 之后合入，文档见 [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md)：

| 域 | 能力 |
|----|------|
| **主题** | 跨 Surface Skin SDK、`hermes skin set`、gateway skin watcher、OSC 11 TUI 背景、`ui_thinking` / `ui_tool` token |
| **TUI Widget** | Widget-app SDK、ambient zone、user-widget 热加载、weather 参考 app、shimmer / widget-grid |
| **Desktop** | Billing 页重做、应用内降级、仓库发现配置、SSH 全链路（含 Windows runtime） |
| **Kanban** | `hermes kanban repair`、WAL TRUNCATE checkpoint |
| **稳定性** | compression route-scoping、stale-budget retry 修复、FTS5 探测加固 |
| **运维** | secrets 一键轮换、`/api/status` component health rollup、status-bar `/battery` |
| **Skills** | Office 捆绑（docx / xlsx / pdf / powerpoint） |

---

<a id="工作区增量2026924-戳文档-2026-10-14"></a>
<a id="section-4"></a>
## 4. 工作区增量（2026.9.24 戳，文档 2026-10-14）

以下在 **monorepo `hermes-dev/hermes-agent`** 已体现，tag 矩阵可能尚未单独发版；以 `git log` / `hermes version` 为准。

| 域 | 变化（相对 0.19 文档行数表） |
|----|------------------------------|
| **内核体积** | `run_agent.py` **~1.5k**、`conversation_loop.py` **~1.9k**（非旧文 ~6.7k / ~5.8k） |
| **SessionDB** | `hermes_state` 拆为 **30+ `hermes_state_*.py`**；见 [STATE_AND_AUXILIARY.md](STATE_AND_AUXILIARY.md) |
| **Auxiliary** | `agent/auxiliary_*.py` 子系统（压缩、session_search、结构化输出、降级） |
| **Gateway** | `delivery_ledger`、`browser_control_broker`、`channel_directory` 等增强 |
| **TUI 桥** | `tui_gateway/` 模块数显著增加（Skin / 事件协议见 SURFACE） |
| **文档** | [CATALOG.md](../../CATALOG.md) 分类；考古 `EXECUTION_FLOW` → `archive/` |

---

<a id="更早版本速览"></a>
<a id="section-5"></a>
## 5. 更早版本（速览）

| CalVer | Semver | 要点 |
|--------|--------|------|
| v2026.4.13 | 0.9.0 | Termux/Android、iMessage、微信、Fast Mode、本地 Web Dashboard、16 平台 |
| v2026.4.8 | 0.8.0 | Google AI Studio、运行时换模、MCP OAuth 2.1、集中日志 |
| v2026.4.3 | 0.7.0 | 可插拔 Memory Provider、credential pools、Camofox、gateway 加固 |
| v2026.3.30 | 0.6.0 | Profiles、MCP server 模式、Docker、fallback chains、飞书/企微 |
| v2026.3.28 | 0.5.0 | Nous Portal 400+ 模型、HF provider、Telegram Topics、Modal、Nix |
| v2026.3.23 | 0.4.0 | 流式、浏览器工具、Skills Hub、插件、7 新消息平台、API server |
| v2026.3.17 | 0.3.0 | 统一流式、插件架构、Anthropic 原生、智能审批、`/browser` CDP、ACP、语音、PII |
| v2026.3.12 | 0.2.0 | 首个 CalVer tag：Gateway、MCP、70+ skills |

---

<a id="按能力域归类跨版本"></a>
<a id="section-6"></a>
## 6. 按能力域归类（跨版本）

| 域 | 里程碑版本 |
|----|------------|
| **多平台 Gateway** | 0.2 → 0.19（**23+** 消息面，以 tag/website 为准） |
| **Kanban / 多 Agent** | 0.13 durable → 0.15 平台化 → 0.17 async subagents → **0.19 live subagent tail** |
| **Memory** | 0.7 Provider → 0.12 Curator → 0.17 memory 工具升级 |
| **UI 面** | 0.9 Dashboard → 0.11 Ink TUI → 0.16 Desktop → **0.19 SSH + 0.19+ Skin/Widget** |
| **Skills / MCP** | 0.4 Hub → 0.15 Nous MCP → 0.16 skills 信任源 → **HEAD office bundle** |
| **安全 / 供应链** | 0.14 Foundation → 0.15 promptware → **HEAD secrets rotation** |
| **性能** | 0.14 冷启动 → 0.15 run_agent 模块化 → **0.19 api_content sidecar** |

---

<a id="读文档时的版本提示"></a>
<a id="section-7"></a>
## 7. 读文档时的版本提示

| 文档现象 | 处理方式 |
|----------|----------|
| 文首写 `0.17.0` / 2026-06-10 | **已过期**；以 `0.19.0` + [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) 补 Surface 层 |
| `run_agent.py` ~6.7k 行 | **已过时**；工作区壳 **~1.5k**，主循环 `conversation_loop.py` **~1.9k**（见 STATE_AND_AUXILIARY / DOC_MAINTENANCE） |
| Memory「六层」叙事 | 以 **三层机制** 为准：`MEMORY_SYSTEM.md` |
| 英文用户手册 | 优先 `website/docs/user-guide/`（Docusaurus，随发版） |

**延伸阅读**: [README.md](README.md) · [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) · [WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md)

<!-- 旧章节锚点兼容：对应内容已校订，见文首导航。 -->
<a id="未发版v2026720-→-工作区2026-07-22-快照"></a>
