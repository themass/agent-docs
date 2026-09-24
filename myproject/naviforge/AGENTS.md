# NaviForge

Browser agent monorepo (`apps/extension`, `apps/host`, `packages/*`). See `docs/AGENT_SYSTEM_DESIGN.md` for architecture.

## Commands

```bash
cd naviforge && npm run check   # typecheck + self-checks (all packages)
cd naviforge && npm run build   # extension + packages
```

## Conventions

- **Plane boundary**: `packages/runtime` has no Chrome APIs; DOM/network live in `apps/extension`.
- **One message entity**: `TraceRecord` only; UI and LLM context are projections.
- **Session**: `@naviforge/session` owns `SessionSnapshot`, `Thread`, live `AgentSession` class.
- **Tests**: `npm run check` per package; e2e under `naviforge/tests/e2e/`.
- **PR titles**: Conventional Commits with scope (`feat(extension): …`).

Follow [`AGENTS.full.md`](../AGENTS.full.md) only for Python `libs/*` work — not for NaviForge TypeScript.
