# Hermes Agent — 新 Feature 设计目录

> **目的**: 把 `hermes-dev/` 内分散的设计 spec、CHANGELOG、版本说明收拢为一张可维护总表。  
> **版本锚点**: Agent **0.19.0** (`v2026.7.20`) · Workspace **2.1.0** (Swarm) · `main` 领先 tag 见下表「未发版」  
> **整理**: 2026-09-10 · 源码路径以 `hermes-dev/` 为准

---

## 0. 设计不变量（读任何 feature 前先记）

来自 `hermes-agent/AGENTS.md`，影响几乎所有新功能能否进 core：

| 不变量 | 含义 | 典型违规 |
|--------|------|----------|
| **Prompt cache 神圣** | 长会话复用缓存前缀；除压缩外不得中途改 system prompt / toolset / memory 注入 | 会话内 `/skills install` 默认 deferred，需 `--now` |
| **Core 窄腰** | 新能力优先 CLI+skill → service-gated tool → plugin → MCP；新 core tool 最后 | 为桌面能力加 `HERMES_DESKTOP` 门控（应 session-scoped toolset） |
| **Surface = Session 属性** | 工具可见性由 session platform 决定，非进程 env | 远程 SSH 后端不应丢 desktop 工具 |
| **角色交替** | 禁止连续同 role message；禁止 loop 中注入 synthetic user | 压缩/投影逻辑需保持 alternation |

---

## 1. 版本时间轴（Agent 内核）

| 版本 | 主题 | 代表能力 |
|------|------|----------|
| **0.19.0** | The Connection Release | Desktop **SSH 远程后端**、**live subagent transcripts**、**api_content sidecar**（cache 字节精确）、delivery-obligation ledger、session-scoped reasoning、`/model --once` |
| 0.18.0 | The Bridge Release | **Raft** channel、Vertex Gemini OAuth、MOA trace JSONL、**/debug** 上传、delegate 继承父 toolsets |
| 0.17.0 | The Reach Release | **async subagents**、iMessage/Photon、图像编辑、Dashboard profile builder、memory 工具升级 |
| 0.16.0 | The Surface Release | **原生 Desktop**、浏览器管理面板、remote-gateway connect、`/undo` |
| 0.15.0 | The Velocity Release | **`run_agent` 模块化**（16k→3.8k LOC）、Kanban→多 Agent 平台、**session_search ~4500×**、ntfy 第 23 平台 |
| 0.14.0 | Foundation | Windows beta、PyPI wheel、**跨 session Claude prompt cache**、`/handoff`、`x_search`、`computer_use` |
| 0.13.0 | Tenacity | **Durable Kanban**、**/goal**、Checkpoints v2、gateway auto-resume、ProviderProfile |
| 0.12.0 | Curator | **后台 Curator 自进化循环**、Teams/元宝、ComfyUI 默认捆绑 |
| 0.11.0 | Interface | **Ink TUI**、Dashboard 插件系统、Bedrock 原生 |
| 0.10.0 | Tool Gateway | Nous Portal 订阅（search / image / TTS / browser） |

### 1.1 未发版（`v2026.7.20` → `main`）

| 域 | 能力 | 文档 |
|----|------|------|
| 主题 | Skin SDK、`hermes skin set`、gateway skin watcher、OSC 11 TUI 背景 | [SURFACE_ARCHITECTURE](../../hermes-dev/hermes-agent/docs/SURFACE_ARCHITECTURE.md) |
| TUI Widget | Widget-app SDK、ambient zone、user-widget 热加载 | 同上 |
| Desktop | Billing 重做、SSH 全链路含 Windows | 同上 |
| Kanban | `hermes kanban repair`、WAL TRUNCATE checkpoint | VERSION_HISTORY |
| 稳定性 | compression route-scoping、stale-budget retry、FTS5 加固 | VERSION_HISTORY |
| Skills | Office 捆绑（docx/xlsx/pdf/ppt） | VERSION_HISTORY |

---

## 2. 产品面矩阵

```text
                    ┌─────────────────────────────────┐
                    │     hermes-agent (Python)        │
                    │  Gateway · run_agent · tools     │
                    └───────────┬─────────────────────┘
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
   ┌──────▼──────┐      ┌───────▼───────┐     ┌───────▼───────┐
   │ CLI / TUI   │      │ Desktop (Elec) │     │ hermes-webui  │
   │ Ink + Rich  │      │ SSH 远程后端   │     │ Dashboard SPA │
   └─────────────┘      └───────────────┘     └───────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  hermes-workspace  │  React 19 全功能工作台
                    │  Chat·Files·Swarm2 │  Zero-fork gateway 对接
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Harness Hub       │  AionCore → Codex/Grok/OpenClaw…
                    └───────────────────┘
```

| 产品 | 路径 | 角色 |
|------|------|------|
| **Agent 内核** | `hermes-dev/hermes-agent/` | Loop、工具、Gateway、Memory、Kanban |
| **Workspace** | `hermes-dev/hermes-workspace/` | 桌面工作台：Chat、Conductor、Swarm2、Harness Hub |
| **WebUI** | `hermes-dev/hermes-webui/` | 浏览器 Dashboard；CLI parity 已完成 |
| **Studio** | `hermes-dev/hermes-studio/` | Content Studio / 技能编排（独立产品线） |
| **Profiles 示例** | `hermes-dev/docs/MULTI_AGENT_PROFILES.md` | github/coder/stocks 三 Profile + Cron |

---

## 3. Workspace 2.x 新设计（重点未整理区）

### 3.1 Zero-fork 架构（2.0.0 ✅）

| 项 | 设计 |
|----|------|
| **目标** | Workspace 直接对接 vanilla `pip install hermes-agent` 0.10+，无 fork gateway |
| **路由** | 双 gateway/dashboard；标准端点 `/v1/models`、`/api/sessions`、`/api/skills`、`/api/jobs` |
| **Memory** | 本地 FS 优先（`HERMES_HOME`），不依赖 gateway |
| **Portable 模式** | OpenAI-compat `/v1/chat/completions` + session 头契约 |

**Session 路由契约**（易错）: `X-Hermes-Session-Key`（UI 路由）≠ `X-Hermes-Session-Id`（gateway 续聊）；后者**不得**依赖 bearer 是否存在 → [workspace-chat-session-routing.md](../../hermes-dev/hermes-workspace/docs/workspace-chat-session-routing.md)

### 3.2 Conductor + Operations（2.0.0 ✅）

| Surface | 路径 | 能力 |
|---------|------|------|
| **Conductor** | `/conductor` | Mission control：spawn mission、分配 worker、实时输出与成本 |
| **Operations** | `/operations` | Agent registry：pause / steer / kill、角色与模型洞察 |

来源：Clawsuite 能力移植；与 Agent 内核 Kanban 互补（产品层编排）。

### 3.3 Swarm2（2.1.0 ✅ + 持续 spec）

**产品命题**: 不是「多聊天窗口」，而是 **Sub-Claude 持久克隆体** — 每条 lane 有 profile、memory、tmux、runtime。

| 文档 | 状态 | 要点 |
|------|------|------|
| [release-2.1.0.md](../../hermes-dev/hermes-workspace/docs/release-2.1.0.md) | ✅ 已发 | Board/Kanban、orchestrator-first 路由、tmux worker、inbox 流 |
| [swarm2-agent-ide-spec.md](../../hermes-dev/hermes-workspace/docs/swarm2-agent-ide-spec.md) | Draft | Hub 卡片（非巨型 chat）、worker IDE tile、lane 概念 |
| [swarm2-autopilot-orchestration-spec.md](../../hermes-dev/hermes-workspace/docs/swarm2-autopilot-orchestration-spec.md) | Spec | 任务分解 → dispatch → checkpoint → 自动 re-prompt；manual/semi/full autopilot |
| [swarm2-memory-framework-spec.md](../../hermes-dev/hermes-workspace/docs/swarm2-memory-framework-spec.md) | Stage 1 | Worker `memory/` 目录契约：IDENTITY/SOUL、mission、episodes、handoffs |
| [swarm2-worker-lifecycle-compaction-spec.md](../../hermes-dev/hermes-workspace/docs/swarm2-worker-lifecycle-compaction-spec.md) | Staged | 250k/400k/500k 软/硬限；handoff → renew tmux session |
| [swarm2-frankengpu-control-plane.md](../../hermes-dev/hermes-workspace/docs/swarm2-frankengpu-control-plane.md) | Brief | Aurora hub + 连线拓扑 UI（Control plane 默认 landing） |

**语义化 Worker 名册**（`swarm.yaml` + `~/.hermes/profiles/<id>/`）:

| Worker | 职责 |
|--------|------|
| orchestrator | 路由、Kanban、delegation、plan |
| builder | 实现、terminal、browser |
| reviewer | 门禁、code review |
| qa | browser smoke、dogfood |
| researcher | web、arxiv、autoresearch |
| km-agent | GBrain、Obsidian 知识库 |
| ops-watch / maintainer / strategist / inbox-triage | 运维、仓库、策略、收件分拣 |

见 [hermes-workspace/AGENTS.md](../../hermes-dev/hermes-workspace/AGENTS.md)。

**已有 API 面**（Swarm2 基础）: `/api/swarm-roster`、`swarm-decompose`、`swarm-dispatch`、`swarm-runtime`、`swarm-chat`、`swarm-tmux-*`。

### 3.4 Harness Hub + AionCore（进行中）

| 项 | 设计 |
|----|------|
| **定位** | Workspace 作为 UI；**AionCore** 提供 ACP 发现与外部 harness 进程兼容 |
| **Chat 导航** | All Agents · Hermes · Codex · Grok · OpenClaw · 其他已安装 runtime |
| **安全** | Renderer 仅调 Workspace API；runtime ID 服务端校验；AionCore 默认 localhost |
| **发现顺序** | `AIONCORE_BIN` → bundled binary → vendor → macOS AionUi bundle |
| **下一里程碑** | 短轮询 → AionCore live event stream；tool/approval/artifact 映射到 command center |

→ [HARNESS_HUB.md](../../hermes-dev/hermes-workspace/docs/HARNESS_HUB.md)

### 3.5 多 Gateway Pool（Spec）

独立 gateway 实例（:8642 nous、:8643 jules…），各绑 profile 级 config/memory/skills；Workspace **Gateway Router** 统一入口。

→ [multi-gateway-pool-spec.md](../../hermes-dev/hermes-workspace/docs/multi-gateway-pool-spec.md)

---

## 4. Agent 内核 Feature（0.15–0.19）

### 4.1 多 Agent 与子代理

| 能力 | 版本 | 机制 |
|------|------|------|
| `delegate_task` | 核心 | 干净上下文、独立预算(50)、受限 toolset；batch mode |
| Leaf vs Orchestrator 子代理 | 核心 | Orchestrator 可再 delegate |
| **async subagents** | 0.17 | 非阻塞委派 |
| **live subagent tail** | 0.19 | 父会话可流式查看子代理 transcript |
| **Durable Kanban** | 0.13→0.15 | 看板持久化 → 多 Agent 平台化 |
| `/handoff` | 0.14 | 运行时切换 provider/人格 |
| `/goal` | 0.13 | 目标追踪 |

→ [MULTI_AGENT_ARCHITECTURE.md](../../hermes-dev/hermes-agent/docs/MULTI_AGENT_ARCHITECTURE.md)

### 4.2 Memory 与学习

| 层 | 内容 |
|----|------|
| **Layer A** | `MEMORY.md` + `USER.md`，会话启动冻结注入 |
| **Layer B** | `state.db` + FTS5 `session_search`（0.15 大幅加速） |
| **Layer C** | Honcho / Mem0 / Hindsight 等可选 Provider（最多一个，不替代 A） |
| **Curator** | 0.12 后台自进化循环（技能/记忆整理） |

→ [MEMORY_SYSTEM.md](../../hermes-dev/hermes-agent/docs/MEMORY_SYSTEM.md)

### 4.3 四 Surface + 流式推理（0.18–0.19）

| Surface | 入口 | 关键事件 |
|---------|------|----------|
| CLI | `hermes` | Rich + reasoning box |
| Ink TUI | `hermes --tui` | `turnController` segment |
| Desktop | Electron | `use-message-stream` + WS |
| WebUI | Dashboard | Transparent Stream / Worklog |

**Gateway 事件区分**:

- `thinking.delta` — **等待态** spinner 文案（非模型推理）
- `reasoning.delta` — **真实推理 token**；turn 结束写入 `msg.thinking`

→ [SURFACE_ARCHITECTURE.md](../../hermes-dev/hermes-agent/docs/SURFACE_ARCHITECTURE.md)

### 4.4 Prompt Cache 与压缩

| 能力 | 说明 |
|------|------|
| **api_content sidecar** | 0.19：精确记录 prompt cache 字节边界 |
| **跨 session cache** | 0.14 Claude prefix 复用 |
| **ContextCompressor** | 会话内压缩（唯一允许 cache break） |
| **compression route-scoping** | HEAD：按路由作用域压缩，避免误伤 |

### 4.5 平台与集成（节选）

| 能力 | 版本 |
|------|------|
| 23+ Gateway 平台（Telegram…ntfy） | 0.15+ |
| Nous Portal Tool Gateway | 0.10 |
| MCP catalog + OAuth 2.1 | 0.8+ |
| Raft channel | 0.18 |
| Desktop SSH 远程 `hermes serve` | 0.19 |
| OpenClaw 迁移 `hermes claw migrate` | 核心 |
| ACP adapter | `acp_adapter/` |

---

## 5. 架构债与进行中设计（高优先级）

### 5.1 Tool Output Artifacts / Context 分离 🔴

**问题**: 工具输出（read_file 大块、terminal log、skill_view）占满 SessionDB，~600k chars tool vs ~7 user messages；UI 被 tool card 淹没。

**方案**: Chat 只保留 **compact tool summary + artifact_id**；完整输出进 Inspector 懒加载。

| 状态 | Spec |
|------|------|
| 📋 Spec | [tool-artifacts-context-plan.md](../../hermes-dev/hermes-workspace/docs/tool-artifacts-context-plan.md) |

与 OpenCode/Codex 的「事件溯源 vs 模型投影」同族问题；对 Hermes **族 A** 尤其关键。

### 5.2 Agent-authored UI State

Agent 显式发射结构化 UI state（如 Inspector artifact 事件），Shell 渲染；无则回退启发式。

→ [agent-authored-ui-state.md](../../hermes-dev/hermes-workspace/docs/agent-authored-ui-state.md)

### 5.3 App Factory 后续（FUTURE-FEATURES）

| 优先级 | Feature | 模式来源 |
|--------|---------|----------|
| 🔴 | Iterative refinement loop（tsc 最多 3 轮） | Anthropic Skills |
| 🔴 | Agent handoffs（结构化上下文传递） | OpenAI Agents SDK |
| 🔴 | Specialized roles（Researcher/Planner/Builder/Validator/Deployer） | App Factory |
| 🟡 | Parallel guardrails（tsc watch 并行） | OpenAI Guardrails |
| 🟡 | Rollback on checkpoint rejection | — |

→ [FUTURE-FEATURES.md](../../hermes-dev/hermes-workspace/FUTURE-FEATURES.md)

---

## 6. 状态图例

| 标记 | 含义 |
|------|------|
| ✅ | 已合入发版或生产可用 |
| 🔄 | 部分落地 / staged rollout |
| 📋 | Spec 已定，实现进行中 |
| 💡 | 路线图 / 未开工 |

---

## 7. 与 Harness 光谱对照

| 维度 | Hermes 落点 | 文档 |
|------|-------------|------|
| 真源族 | A SessionDB | [21-session-message-architecture](../../OpenHarness/docs/framework-comparison/21-session-message-architecture.md) |
| 中途输入 | interrupt（可配 steer/queue） | [14-loop-interjection](../../OpenHarness/docs/framework-comparison/14-loop-interjection.md) |
| Plan | `/plan` skill + todo 工具 | [05-plan-mode](../../OpenHarness/docs/framework-comparison/05-plan-mode.md) |
| 压缩 | ContextCompressor + Curator | [07-compression](../../OpenHarness/docs/framework-comparison/07-compression.md) |
| 多 Agent | delegate + Kanban + Swarm2 | [04-multi-agent](../../OpenHarness/docs/framework-comparison/04-multi-agent.md) |
| 渠道 | Gateway 23+ | [09-channels](../../OpenHarness/docs/framework-comparison/09-channels.md) |

---

## 8. 维护约定

1. **版本以 tag 为准** — `hermes version` / `hermes_cli.__version__`；`main` 领先见 VERSION_HISTORY「未发版」。
2. **Canonical 不进本目录复制** — 内核细节改 `hermes-agent/docs/*`；Workspace 改 `hermes-workspace/docs/*`；本目录只做 **索引 + 跨面叙事**。
3. **新 spec 入库** — 在 `hermes-workspace/docs/` 或 `hermes-agent/docs/` 落 spec 后，在本表 §3–§5 增一行并链过去。
4. **下一步文档债** — DESIGN_THINKING_SERIES（九幕导读）、Archify 图解集、`ARCHITECTURE_PART1` 源码级分章（对齐 Codex/OpenCode 体例）。

---

## 9. 快速检索

| 你想搞懂… | 读 |
|-----------|-----|
| 为什么 session 续聊断了 | §3.1 session routing 契约 |
| Swarm 和 delegate 区别 | §3.3（持久 clone）vs §4.1（一次性子代理） |
| Memory 到底几层 | §4.2 三层主模型（非六层） |
| thinking vs reasoning | §4.3 事件表 |
| 外部 Codex 怎么进 Workspace | §3.4 Harness Hub |
| context 爆掉怎么办 | §5.1 artifact 分离 |
| 夜间 App Factory | §5.3 FUTURE-FEATURES |
