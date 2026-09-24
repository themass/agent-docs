# Hermes Atlas 社区热点整理

> **来源**: [hermesatlas.com](https://hermesatlas.com/)（社区地图，每周策展）  
> **整理日期**: 2026-08-04（站点快照）  
> **说明**: Star /「this week」为 Atlas 展示快照，会变动；安装前请点进仓库看 README 与兼容性。  
> **本地文档锚点**: Hermes `0.19.0`（`v2026.7.20`）；Atlas hero 已标 **v0.20.0**（`v2026.8.3`）— 以 `hermes version` 为准。

---

## 站点概览

- **定位**: Nous Hermes Agent 生态 — tools、skills、plugins、workspaces、memory 等 **12 类**、**221** 仓库（Atlas 2026-08-04）
- **官方核心**: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — Atlas hero **~225.1k★**、47 built-in tools、16 platforms、20+ LLM providers（以 GitHub 实时为准）
- **本周 featured（2026-08-03）**: [Eynzof/Hermes-CN-Desktop](https://github.com/Eynzof/Hermes-CN-Desktop) — 中文社区 Tauri + Rust + React 桌面客户端（Windows / macOS），~1.4k★
- **生态叙事**: Atlas 首页「State of Hermes — July 2026」— 约 216k★ 核心仓、百万星生态、velocity → surface → reach → judgment 发版节奏

### Handbook（ evergreen 指南，2 篇）

| 指南 | 内容 |
|------|------|
| Hermes Agent beginner guide | 安装、选模型、第一个 workflow、核心学习循环 |
| Hermes Agent Memory Guidebook | 原生 memory vs 官方 MemoryProvider vs 社区（GBrain、Mnemosyne 等） |

---

## 一、Workspaces & GUI（聊天入口热度）

Atlas **Workspaces & GUIs** 类目按 star 排序的代表（2026-08-04）：

| 仓库 | Stars（快照） | 一句话 |
|------|---------------|--------|
| [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) | **~16.9k** | 「从 Web/手机用 Hermes 的最佳方式」— **轻量聊天首选** |
| [fathah/hermes-desktop](https://github.com/fathah/hermes-desktop) | ~13.7k | 安装、配置、聊天一体化桌面伴侣 |
| [EKKOLearnAI/hermes-studio](https://github.com/EKKOLearnAI/hermes-studio) | ~9.7k | Web 仪表盘：多平台聊天、会话、定时任务、渠道配置、用量分析 |
| [outsourc-e/hermes-workspace](https://github.com/outsourc-e/hermes-workspace) | ~6.3k | 原生 Web 工作台：Chat + Terminal + Memory + Skills + Inspector |
| [dodo-reach/hermes-desktop](https://github.com/dodo-reach/hermes-desktop) | ~2.0k | Mac 原生，真实 SSH/终端/会话数据 |
| [Eynzof/Hermes-CN-Desktop](https://github.com/Eynzof/Hermes-CN-Desktop) | ~1.4k | **本周 featured** — Windows 优先的中文桌面端（Tauri） |
| [abundantbeing/hermes-browser-extension](https://github.com/abundantbeing/hermes-browser-extension) | ~1.2k | Chromium 侧栏，把浏览器上下文接到本地/远程 Hermes |

**解读**: Star 仍集中在 **轻量 WebUI / Desktop 聊天壳**；全功能 Workspace 更偏「控制台」。Chat 实时性与 Gateway 行为见 [WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md)、[CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md)。

---

## 二、Skills & Skill Registries（近期高热）

### 社区 / 元技能

| 仓库 | Stars | 用途 |
|------|-------|------|
| [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) | ~27.2k | 754 条网络安全 skills（MITRE/NIST 等映射） |
| [obra/superpowers](https://github.com/obra/superpowers) | ~265.9k | Agentic skills 框架 + 软件方法论（agentskills.io 生态） |
| [Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill) | ~7.1k | 自然语言 → draw.io 图 |
| [AMAP-ML/SkillClaw](https://github.com/AMAP-ML/SkillClaw) | ~2.3k | Skills 集体进化（Agentic Evolver） |
| [mohitagw15856/pm-claude-skills](https://github.com/mohitagw15856/pm-claude-skills) | ~1.3k | 822 条专业 agent skills，可粘贴到 Hermes / Claude Code |
| [internet-court/internet-court-skill](https://github.com/internet-court/internet-court-skill) | ~1.5k | Agent 间 commerce：mandate、x402、escrow |
| [Romanescu11/hermes-skill-factory](https://github.com/Romanescu11/hermes-skill-factory) | ~487 | 观察工作流 **自动生成** skills |
| [ZeroPointRepo/youtube-skills](https://github.com/ZeroPointRepo/youtube-skills) | ~484 | YouTube 字幕/搜索/频道 skills |
| [Cranot/super-hermes](https://github.com/Cranot/super-hermes) | ~357 | 教 Hermes 写分析型 prompt 的 skills |
| [AkoliteZA/hermes-agent-idea-workflow](https://github.com/AkoliteZA/hermes-agent-idea-workflow) | ~247 | 想法 → 设计文档 → 实现交接 |
| [willingning-coder/eagle-eye](https://github.com/willingning-coder/eagle-eye) | ~25 | 5 层 skill 检索（硬触发 + FTS5 + 同义词 + embedding + RRF） |
| [Sahil-SS9/hermes-simplify-swarm](https://github.com/Sahil-SS9/hermes-simplify-swarm) | ~11 | 多 Agent 代码简化（类 Claude `/simplify`） |
| [Sahil-SS9/hermaguard](https://github.com/Sahil-SS9/hermaguard) | ~17 | 对抗式只读 Code Review（3 路 subagent） |
| [Sahil-SS9/hermes-memlock](https://github.com/Sahil-SS9/hermes-memlock) | ~9 | 压缩后 **重新注入** 常驻指令 |
| [Sahil-SS9/Toolaria](https://github.com/Sahil-SS9/Toolaria) | ~13 | 超大 tool result 落盘，防 context 洪水 |
| [amanning3390/hermeshub](https://github.com/amanning3390/hermeshub) | ~11 | 社区 skill 浏览、搜索、一键安装 |

**与内置 skill 机制**: Agent 通过 `skill_manage` 创建/修补 skill 的规则见 [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) §11；Prompt 侧索引见 [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md)。

### 官方 Bundled（仓库内，非 Atlas 第三方）

路径：`hermes-agent/skills/`、`website/docs/user-guide/skills/` — software-development、research、github、creative 等 **bundled** 与 **optional**。发版默认集在 v0.16 曾 **精简**（见 [VERSION_HISTORY.md](VERSION_HISTORY.md)）。

---

## 三、Memory & Context

| 仓库 | Stars | 说明 |
|------|-------|------|
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | ~62.5k | 官方 Hermes MemoryProvider（托管或自托管 OSS） |
| [garrytan/gbrain](https://github.com/garrytan/gbrain) | ~27.7k | 图 + synthesis；OpenClaw/Hermes「大脑」层 |
| [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | ~28.8k | 官方 provider；向量图引擎、context fencing |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | ~27.9k | 官方 provider；`viking://`、L0/L1/L2 分层加载 |
| [topoteretes/cognee](https://github.com/topoteretes/cognee) | ~29.7k | 自托管知识图长期记忆（Atlas skills 类目亦收录） |
| [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | ~19.1k | retain / recall / reflect |
| [campfirein/byterover-cli](https://github.com/campfirein/byterover-cli) | ~4.9k | 官方 provider；git 式 memory 版本 |
| [mnemosyne-oss/mnemosyne](https://github.com/mnemosyne-oss/mnemosyne) | ~2.0k | 零依赖亚毫秒记忆（仓库已迁至 mnemosyne-oss） |
| [ClaudioDrews/memory-os](https://github.com/ClaudioDrews/memory-os) | ~1.3k | 七层 memory：Qdrant、结构化事实、wiki 策展 |

**会话内召回**: 内置 `session_search` 为 FTS5 + 结构化切片（**无 LLM 摘要**）；见 [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) §12。Memory 三层模型见 [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)。

---

## 四、Plugins & Extensions

| 仓库 | Stars | 说明 |
|------|-------|------|
| [bit64k/cronalytics](https://github.com/bit64k/cronalytics) | ~998 | 定时任务用量与成本归因 |
| [jau123/MeiGen-AI-Design-MCP](https://github.com/jau123/MeiGen-AI-Design-MCP) | ~1.7k | 图像 MCP + 1400+ prompt 库 |
| [robbyczgw-cla/hermes-web-search-plus](https://github.com/robbyczgw-cla/hermes-web-search-plus) | ~360 | 多源搜索路由（Serper/Tavily/Exa…） |
| [42-evey/hermes-plugins](https://github.com/42-evey/hermes-plugins) | ~365 | Goal、桥接、选模、成本控制 |
| [stainlu/hermes-labyrinth](https://github.com/stainlu/hermes-labyrinth) | ~301 | 只读可观测：journeys / crossings |
| [runta-dev/clawshell](https://github.com/runta-dev/clawshell) | ~322 | OpenClaw/Hermes 运行时安全层（PII / 凭据） |

插件加载与 hook 执行见 [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md)。

---

## 五、Multi-agent & Orchestration（Atlas §06 摘录）

| 仓库 | Stars | 说明 |
|------|-------|------|
| [builderz-labs/mission-control](https://github.com/builderz-labs/mission-control) | ~5.9k | 自托管编排：多 agent workflow、花费监控 |
| [agent-of-empires/agent-of-empires](https://github.com/agent-of-empires/agent-of-empires) | ~3.0k | TUI/Web 控制面，管理多种 coding agent CLI |
| [ilkhamov/opencode-hermes-multiagent](https://github.com/ilkhamov/opencode-hermes-multiagent) | ~1.7k | 17 个专职 agent 角色模板 |
| [linke-ai/hermes-agent-team](https://github.com/linke-ai/hermes-agent-team) | ~170 | 基于 profiles + MCP + Kanban 的本地多 agent 协作 Web |

委派与子 agent 运行时见 [MULTI_AGENT_ARCHITECTURE.md](MULTI_AGENT_ARCHITECTURE.md)。

---

## 六、Curated Lists（Atlas 手册入口）

站点 **6 条 Curated lists** + **2 篇 Handbook guides**（见上文），常用起步：

1. **Best memory providers** — 长期语义记忆、图检索  
2. **Top skills** — agentskills.io 生态最热  
3. **Deployment options** — Docker / Nix / systemd / K8s Helm  
4. **Multi-agent frameworks** — 舰队 / swarm / control room  
5. **Developer tools** — CLI、迁移、token 统计  
6. **Workspaces & GUIs** — 见本文 §一  

---

## 七、使用建议

1. **先定 Hermes 版本**（`hermes version`），再看 skill/plugin README 的最低版本；Atlas 展示版本可能领先本地 monorepo 一两个 tag。  
2. **技能安装**: 官方 `hermes skills` / Dashboard；社区 [hermeshub](https://github.com/amanning3390/hermeshub)、[skills.sh](https://skills.sh)（v0.15.1+ 集成）。  
3. **安全**: Atlas 标注 security reviewed，第三方仍建议 `hermes doctor` + 沙箱 / [clawshell](https://github.com/runta-dev/clawshell) 类运行时防护。  
4. **与内置 skills 关系**: bundled 在仓库内；Atlas 列的是 **社区扩展**，不自动安装。  
5. **文档对照**: 改 Hermes 本身行为以仓库 `docs/` Canonical 为准；Atlas 是 **生态索引**，不保证与某一 tag 的 API 逐字对齐。

**本地 Canonical 对照**:

| 域 | 文档 |
|----|------|
| Skills / `skill_manage` | [SKILLS_SYSTEM.md](SKILLS_SYSTEM.md) · [TOOLS_SYSTEM.md](TOOLS_SYSTEM.md) §11 |
| Plugins | [PLUGINS_SYSTEM.md](PLUGINS_SYSTEM.md) |
| Memory | [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) |
| CLI / Gateway / 消息并发 | [CLI_GATEWAY_SYSTEM.md](CLI_GATEWAY_SYSTEM.md) |
| Prompt / skill 索引 | [PROMPT_SYSTEM_ARCHITECTURE.md](PROMPT_SYSTEM_ARCHITECTURE.md) |
| Workspace vs WebUI | [WORKSPACE_VS_WEBUI.md](WORKSPACE_VS_WEBUI.md) |
| 版本与发版 | [VERSION_HISTORY.md](VERSION_HISTORY.md) · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md) |
