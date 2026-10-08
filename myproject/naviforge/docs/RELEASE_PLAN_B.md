# Release plan B — product backlog (P5 Cloud excluded)

Status as of **0.1.0** store track. **P5 full cloud** intentionally out of scope.

## Phase 0 — Store / narrative ✅

| Item | Status |
|------|--------|
| Playbook auto-forge after successful Run | ✅ `playbook-forge-after-run.ts` |
| BYOK default + managed login toggle (Advanced) | ✅ |
| `networkEnabled` default off | ✅ |
| Version 0.1.0 | ✅ |

## Phase 1 — 沉淀闭环 ✅ (Skill auto-generate ❌ by design)

| Item | Status |
|------|--------|
| Learn **Site Recipe** from `recordedActions` (download / media intents) | ✅ `recipe-from-run.ts` + run-supervisor |
| Manual Recipe templates (Options) | ✅ unchanged |
| Host **`scripts/download-hls.sh`** seed on workspace init | ✅ `apps/host/script-templates.ts` |
| Post-run hint for media → ffmpeg / `script_save` | ✅ run note |
| Auto-generate **Skill** from runs | ❌ not planned — import Skills only |

## Phase 2 — Toolkit & permissions ✅

| Item | Status |
|------|--------|
| **⌥N `open-toolkit`** → Options **工具** tab | ✅ `openToolkitPage()` |
| Toolkit one-click (panel + shortcuts ⌥A/⌥S/…) | ✅ existing `toolkit-panel` + background commands |
| **`optional_host_permissions`** + runtime request | ✅ `host-permissions.ts` + first Run |

## Phase 3 — P5 Cloud

**Ignored** per product decision.

## Phase 4 — Engineering ✅ / ongoing

| Item | Status |
|------|--------|
| `@page-agent/page-controller` npm pin | ✅ `1.12.4` |
| Runtime typecheck fixes (fetch batch, network list) | ✅ |
| `docs/THIRD_PARTY_NOTICES.md` | ✅ |
| E2E | ✅ existing `tests/e2e/*` — run `npm run test:e2e` before release |
| `npm run check` full monorepo | run locally; extension typecheck may still pull workspace TS project |

## Verify before upload

```bash
cd docs/myproject/naviforge
npm install
npm run build -w @naviforge/extension
npm run zip -w @naviforge/extension
npm run test:e2e   # optional gate
```

Clean profile: grant site access on first Run → DOM task → check **Automation → Playbooks** and **Site shortcuts**.
