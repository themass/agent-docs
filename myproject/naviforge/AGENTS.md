# NaviForge

**通用浏览器 Agent** monorepo（`apps/extension`, `apps/host`, `packages/*`）。  
架构：`docs/AGENT_SYSTEM_DESIGN.md` · 内核决策：`docs/AGENT_KERNEL_INTEGRATION_DECISION.md` · **工程纪律：`docs/RUNTIME_ENGINEERING_RULES.md`**

## Commands

```bash
cd docs/myproject/naviforge && npm run check -w @naviforge/runtime
cd docs/myproject/naviforge && npm run check -w @naviforge/extension
cd docs/myproject/naviforge && npm run build
```

## Conventions

- **Plane boundary**: `packages/runtime` has no Chrome APIs; DOM/network live in `apps/extension`.
- **One message entity**: `TraceRecord` only; UI and LLM context are projections.
- **Session**: `@naviforge/session` owns `SessionSnapshot`, `Thread`, live `AgentSession` class.
- **Tests**: `npm run check` per package; e2e under `tests/e2e/`; golden 任务句式在测试/fixture，**不**写进 runtime。
- **PR titles**: Conventional Commits with scope (`feat(extension): …`).

### Runtime 纪律（必守）

1. **禁止 host 分支** — 不对具体域名写 `if`、不写死验收站进 runtime；SiteRecipe 仅 **数据** 里带 `hosts`。
2. **新行为先写 Deliverable Plan** — 先改 `deliverable.ts` 的 PLAN / preflight / Verify 叙事，再加 hook；一次 Run 一个 `deliverable`。
3. 详见 [`docs/RUNTIME_ENGINEERING_RULES.md`](docs/RUNTIME_ENGINEERING_RULES.md)。

Follow [`AGENTS.full.md`](../../AGENTS.full.md) only for Python `libs/*` work — not for NaviForge TypeScript.
