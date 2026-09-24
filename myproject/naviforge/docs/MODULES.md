# NaviForge 模块拆分与迭代

当前架构叙事以 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) 为准。本文件只约束**何时拆包**，不重复循环 / 审计 / 工作集设计。

## 为什么不一次拆满

长期目标仓结构见下文。工程上应**按交付切模块**，否则会出现：

- 空 `package.json` 无人维护；
- import 边界早于真实需求；
- Phase 0 被 Host/Cloud/MCP 拖慢。

规则：**一个迭代只新增「本迭代必须独立版本/独立测试」的包**。同一 Phase 内能合在 `runtime` 的就不拆。

## 推荐模块边界

### 长期目标（产品完整时）

```text
apps/extension          UI + MV3 胶水（薄）
apps/host               localhost task bridge / stdio MCP Server / MCP Client
apps/cloud-console      团队与市场（Phase 5）

packages/shared         协议与类型（最早出现，永远轻）
packages/policy         Task scope / HITL / URL drift / navigation guard
packages/runtime        Orchestrator / PromptCompiler / Checkpoint
packages/observe        Compact snapshot for prompt budget
packages/media-plane    m3u8/mp4 hint classification
packages/extract        Page list + media merge
packages/session        Portable audit export schema
packages/dom-plane      DomPlane 接口 + page-agent Adapter
packages/network-plane  CDP Network + scrub + digest（Phase 1）
packages/skill-runtime  安装/路由/权限（Phase 2）
packages/playbook       AST / Runner / Forge / Repair（Phase 3）
packages/ui             可选：Side Panel 共享组件（有重复再抽）
```

### 当前实际模块（2026-08-13）

| 模块 | 职责 | 不做什么 |
|------|------|----------|
| `apps/extension` | Side Panel、SW、content、设置、Plane 实现、工具箱 | 不把 policy 写进 content script |
| `apps/host` | localhost MCP 桥 | 不是 runtime 硬依赖 |
| `packages/shared` | `ToolResult`、`ToolCall`、**agent-tools 单源** | 不依赖 Chrome API |
| `packages/policy` | Scope / HITL / URL drift / 导航类 click | 不调 LLM |
| `packages/dom-plane` | `DomPlane` 接口 | 不调 LLM；不碰 Network |
| `packages/network-plane` | digest / wait / intercept 模型 | CDP 监听在 extension |
| `packages/runtime` | 循环、prompt、工作集、LLM、只读叶 Agent | 不直接操作 DOM |
| `packages/observe` | `compactSnapshotForPrompt` | 不依赖 extension |
| `packages/media-plane` | 媒体 URL hints | 不抓 CDP |
| `packages/extract` | 结构化列表抽取 | 不执行 DOM 写 |
| `packages/session` | TraceRecord 账本类型 / JSONL | 不做 `chrome.storage` |
| `packages/skill-runtime` | L1 目录、`skill_load` | 不执行远程 JS |
| `packages/playbook` | Forge / 确定性 Runner | 不走 LLM |

### Runtime Plane 与工具前缀（2026-08-17）

| Plane | 工具前缀 / catalog | 实现 |
|-------|-------------------|------|
| `dom-plane` | `dom_*`, `dom_read` | `chrome-dom-plane.ts`, `content.ts` |
| `network-plane` | `network_read`, `network_intercept` | `chrome-network-plane.ts`, `network-recorder.ts` |
| `tabs-plane` | `tabs_*` | `chrome-tabs-plane.ts` |
| `search-plane` | `web_search` | `web-search.ts` |
| `script-plane` | `script_*` | `chrome-script-plane.ts` |
| `workspace-plane` | `workspace`, `workspace_*` | `local-workspace.ts` + host RPC |

MCP 协议适配留在唯一消费者 `apps/host`，没有空壳 `mcp-bridge`。`cloud-console` / `packages/ui` 未建。

**合并理由**：PromptCompiler 与 Orchestrator 在 Phase 0–1 边界会来回改；拆成两个包只会增加 churn。Phase 3 若 Prompt 需要独立评测再拆 `prompt-compiler`。

## 依赖方向（强制）

```text
extension → runtime → {policy, observe, extract, media-plane, dom-plane, network-plane} → shared
                ↘ shared ↗
extension ⇄ localhost Host ⇄ external MCP servers
runtime ↛ extension
dom-plane ↛ runtime
policy ↛ runtime
```

Network / Skill / Playbook / MCP 只能被 `runtime`（或更上层 app）调用，彼此默认不互相依赖。

## 迭代切分（怎么做合适）

### Phase 0 — 技术验证（当前骨架）

**交付**：单 tab，自然语言 → DOM 动作 → 可见结果。

**包**：`extension` + `shared` + `dom-plane` + `runtime` + `demos/test-site`

**复用**：

- WXT 脚手架与扩展布局：参考 `page-agent/packages/extension`
- DOM：`@page-agent/page-controller`
- LLM HTTP：可参考 `@page-agent/llms` 或自写 ~50 行 OpenAI-compatible client（优先复用）

**退出标准**：单 tab 自然语言 → DOM 动作 → 可见结果（已达成）。

### Phase 1 — 可用 Agent

**新增**：`packages/network-plane`

**仍合在 runtime**：完整状态机、History、暂停/接管、Context Manager。

**复用对照**（抄行为，不当依赖）：`pagenter-ext` 的 debugger Network 录制与脱敏；Chrome `debugger` API。

### Phase 2 — Skills

**新增**：`packages/skill-runtime`。Bundled 正文在扩展 `BUNDLED_SKILLS`（`apps/extension/src/skills/catalog.ts`）。用户 Skill 在 Host 工作区 `~/NaviForge/skills/`，不在本仓库。

**形态**：Instruction / Template Skill（Markdown + `skill.json`）。不执行远程 JS。

**复用思路**：技能包形态对齐 Cursor/Claude `SKILL.md` 惯例；路由逻辑自研（小）。

### Phase 3 — Forge / Playbook = MVP

**新增**：`packages/playbook`

**从 runtime 迁出**：Teach 轨迹 → AST、deterministic Runner、最小 Repair。

**复用**：YAML 用现成解析器（如 `yaml`）；表达式只用 `${inputs.x}` + JSONPath（现成库），禁止 `eval`。

### Phase 4 — MCP + Host

**新增**：`apps/host`。先不拆 `packages/mcp-bridge`；出现第二个 MCP 协议消费者时再抽。

**复用**：

- `@modelcontextprotocol/server` + `@modelcontextprotocol/client`
- 可对照 `page-agent/packages/mcp`（扩展侧 MCP 桥）
- Native Messaging 标准模式

### Phase 5 — 产品化

**新增**：`apps/cloud-console`（独立 app，可另仓）

扩展与 Host 不绑死云端。

## 和长期目标仓的差异

| 长期目标 | 本工程做法 |
|----------|------------|
| 一开始列出全部 packages | 交付到了再 mkdir |
| 独立 `prompt-compiler` | 仍在 `runtime`（工作集已单文件，未拆包） |
| 独立 `ui` | Side Panel 写在 `extension` |
| `cloud-console` / `host` 并列 | Host 已建；Cloud 仍延后 |

架构以 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md) 为准；本文件只约束**实现节奏**。

## 建议的人员/并行切法（若多人）

| 轨道 | 模块 | 可并行条件 |
|------|------|------------|
| A | `dom-plane` + test-site | 可最先开工，接口先冻结 |
| B | `runtime` LLM + schema | 依赖 shared schema |
| C | `extension` 壳 | 可先 mock DomPlane |
| D | `network-plane` | Phase 1，依赖 runtime tool registry |

单人时顺序：**shared schema → dom-plane → runtime → extension 接通 → test-site 验收**。
