# NaviForge

本地优先的 Chrome 浏览器 Agent。扩展可独立运行；需要 MCP/本地进程能力时再启动
NaviForge Host。设计见 `../docs/CHROME_EXT_BROWSER_AGENT_DESIGN.md`。

## 安装 / 构建

```bash
cd naviforge
npm install
npm run check
npm run build    # → apps/extension/dist/chrome-mv3
```

加载：`chrome://extensions` → 开发者模式 → **重新加载** `apps/extension/dist/chrome-mv3`。

## 测试

```bash
npm run demo:site   # http://localhost:4177
npm run test:e2e    # Playwright（test-site + 解析/断言）
```

Side Panel：选模型 → 填任务 → **Run Agent**。运行中可用 **纠偏 / 下一问 / Pause / Stop**。
**Settings**（同一 Side Panel 内切换）：Agent / 插件管理 / 自动化 / 设置。

## 本地 Host / MCP

```bash
export NAVIFORGE_HOST_TOKEN="$(openssl rand -hex 24)"
npm run host
```

在 **Settings → MCP** 填入同一 token 并启用 Host。

## 模块

```text
apps/extension
apps/host
packages/{shared,dom-plane,runtime,network-plane,skill-runtime,playbook,policy,observe,extract,media-plane,session}
demos/test-site
```

| 阶段 | 状态 |
|------|------|
| P0 DOM Chat | ✅ |
| P1 Network + Pause/Stop（debugger；body 可选 32KB JSON/text） | ✅ |
| P2 Instruction Skills（内嵌 + 导入 + 工具白名单） | ✅ |
| P3 Playbook（锻造、参数化、重放、DOM 文本断言） | ✅ |
| P4 Host/MCP（stdio Server、任务桥、外部 MCP Client） | ✅ |
| P5 Cloud | ❌ |

## Agent 能力摘要

- **27 个工具**：DOM / Network / System / MCP
- **多模型 Profile**、Vision 截图、线程记忆压缩
- **纠偏 / 下一问 / HITL / Pause / Stop**（含 network_wait 取消）
- **策略**：当前页 scope、导航点击拦截、URL drift 回滚
- **Preflight**：Run 前检查 API Key / 标签 URL / content script / debugger
- **Skill**：默认仅提示；可选开启硬白名单（Settings → Privacy）
- **高亮**：`dom_mark_topn` 启发式标记 + overlay TOP 标签
- **BLOCKED**：模型/API 拒绝时会展示原因（非页面错误）

详见 `docs/MODULES.md`、`docs/AGENT_MCP_RUNTIME_DESIGN.md`。架构优化 backlog 见 `docs/ARCHITECTURE_OPTIMIZATION.md`。
