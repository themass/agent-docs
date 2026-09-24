# 开源复用清单

原则：**依赖库 / 适配层**，不把第三方仓库复制进 `naviforge/`。对照闭源仅作行为参考。

## 直接依赖（推荐）

| 能力 | 项目 | 用法 | 何时引入 |
|------|------|------|----------|
| DOM snapshot / click / type | [alibaba/page-agent](https://github.com/alibaba/page-agent) `@page-agent/page-controller` | `dom-plane` Adapter | Phase 0 |
| 扩展工程脚手架 | 同上 `packages/extension`（WXT） | 抄结构，自有包名 | Phase 0 |
| OpenAI-compatible LLM | `@page-agent/llms` 或自写 fetch 客户端 | `runtime` Provider | Phase 0 |
| Schema | `zod` | `shared` | Phase 0 |
| 扩展构建 | `wxt` + React | `apps/extension` | Phase 0 |
| 本地 DB | `dexie`（IndexedDB） | History / checkpoint | Phase 0–1 |
| YAML Playbook | `yaml` + `jsonpath`（或同类） | `playbook` | Phase 3 |
| MCP | `@modelcontextprotocol/server` + `@modelcontextprotocol/client` v2 | `apps/host` | Phase 4 |

本机路径：`../page-agent`（已在 monorepo 根旁）。

## 行为参考（不 import）

| 能力 | 来源 | 注意 |
|------|------|------|
| Network 录制 / Body / 脱敏 | `../pagenter-ext-1.8.0-chrome` | 闭源对照；自行用 `chrome.debugger` 实现 |
| Agent 多步循环 / 恢复策略 | `../browser-use` | Python；只借思路与 Prompt 分层 |
| 扩展 MCP Server 形态 | `page-agent/packages/mcp` | 行为对照；协议实现使用官方 SDK |

## 明确不依赖

| 项目 | 原因 |
|------|------|
| Playwright / Puppeteer 作为扩展运行时 | 产品跑在用户真实 Chrome 标签页，不是新起浏览器 |
| 整仓 fork page-agent | 用 Adapter；升级跟官方包 |
| 远程可执行 Skill JS | MV3 禁止；Instruction/Template 或 Host 沙箱 |
| WebLoom / TabForge 等产品代码 | 定位重叠，只作竞品基线 |

## Phase 0 最小依赖集（预期）

```text
wxt, react, zod
@page-agent/page-controller
(可选) @page-agent/llms
dexie（若 Phase 0 就要 checkpoint 持久化；否则可先 memory + chrome.storage）
```

其余一律延后。
