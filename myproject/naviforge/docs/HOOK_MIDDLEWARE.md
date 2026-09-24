# Hook / middleware design

Status: **implemented**. Named checkpoints on one `AgentCtx`. No Cordis, no `next()` onion.

## Center objects

Two objects, assembled separately. This is the same split as Pi (`Agent` vs `AgentContext`), MAF (`Agent` vs `AgentContext`), and DSH (seams vs per-turn ctx) — not a plugin bus.

### `Agent` — capability bag (once per `runAgent`)

Built from `AgentOptions` in `packages/runtime/src/agent-ctx.ts`. `runAgent(opts)` is `new Agent(opts)` then the loop. `agent.run()` is the same loop.

| Field | Role |
|---|---|
| `planes` | `{ dom, network?, tabs?, search?, scripts?, workspace? }` — I/O seams |
| `llm` | Model config |
| `skills` / `mcpTools` / `skillGuidance` | **Mutable** catalogs. `onStart` / `beforeModel` add or drop capabilities here |
| `policy` | HITL mode, DOM inject / network intercept, skill allowlist, URL-drift rollback |
| `limits` | maxSteps, same-failure, action-loop, wall clock, token budget |
| `hooks` | `HookPipeline` (stock + `opts.hooks`) |
| `hitl` / `queue` / `pause` / `signal` | Controllers |
| `callMcpTool` / `mainProbe` | Host callbacks |

Hooks that should persist across turns mutate **`agent.mcpTools` / `agent.skills` / `agent.skillGuidance`**. Each `beforeModel` starts with `syncFromAgent()` (copies those onto `ctx`, rebuilds `ctx.tools`). Extra `beforeModel` hooks may then filter the **this-turn** copy.

### `AgentCtx` — per-run working set (every hook gets this)

Created after the first snapshot. One object, not a family of mini-context types.

| Field | Role |
|---|---|
| `agent` | Back-pointer to the bag |
| `ledger` | Append-only notes; policy / HITL read `all()` |
| `task` / `taskId` / `taskScope` / `snap` | Current work |
| `turnIndex` / `runTotalTokens` | Loop counters |
| `prompt` | `{ system, user, thread?, loadedSkillText? }` — rewrite in `onStart` / `beforeModel` |
| `tools` | `buildChatTools` result sent to the LLM this turn |
| `skills` / `skillGuidance` / `allowedTools` | Per-turn copies (reset from Agent each `beforeModel`) |
| `messages` | Projected working set (`projectTraceRecords(ledger.all())`). **`compileUser` uses only this** — never raw payloads |
| `imageDataUrl` / `networkText` | Multimodal + network digest |
| `completion` / `decision` / `toolCall` / `toolResult` | Current model/tool payload; `beforeTool` may change `toolCall.arguments` |
| `gates` | Stock loop-gate counters (`loadedSkillIds`, CSP, obs dedupe, action-loop, list hints, `taskHintIssued`). Do not add more `*Issued` flags on the ctx top level |
| `metadata` | Escape hatch for extra hooks |

Helpers: `emit`, `note`, `recover`, `compileUser`, `syncFromAgent`, `syncTools`, `refreshNetwork`, `toExecContext()`.

```text
AgentOptions
    │  assemble once
    ▼
  Agent  (planes, llm, skills, mcpTools, policy, limits, hooks)
    │  first snapshot
    ▼
  AgentCtx  (ledger, prompt, tools, messages, snap, gates)
    │  passed to every hook
    ▼
  HookPipeline
```

## Phases

First non-`continue` wins (Chain of Responsibility). Notify-only phases run every hook.

| Layer | Phase | Mutates / decides |
|---|---|---|
| Agent | `onStart` / `onStop` | system prompt, skills, tools at run start; observe stop |
| Loop | `beforeStep` / `afterStep` | task steering `#hint`; observe |
| Model | `beforeModel` | project ledger → `messages` + `prompt.user`; fold; budget stop; extra hooks rewrite prompt/tools/skills |
| Model | `afterModel` | require exactly one native tool call → `decision` (`proceed` / `retry_turn` / `stop`) |
| Model | `onModelError` | transport failure after HTTP retry → usually HITL |
| Tool | `beforeTool` | args, skip, allowlist, sensitive HITL, CSP/obs/action-loop |
| Tool | `afterTool` | **Merge** notes; `forceAsk` / `markCsp` stick if any hook set them; sticky skill / list hints / obs+loop counters |

`HookDecision`: `continue | skip_tool | ask_user | stop | retry_turn | replace_decision`.

Stock order (then `opts.hooks`): task-hint → working-set → protocol → model-error → tool-outcome → tool-state → skill-allowlist → sensitive-tool → duplicate-skill → csp-skip → dedupe-observation → action-loop.

## What stays in the loop

Deterministic list/mark/page-read preflight, HITL `waitForReply`, follow-up queue, pause, vision screenshot I/O, URL drift inside `execTurn`. HTTP 408/429/5xx stays `recovery.retry` (library, not a hook). Privacy inject/intercept stays inside tool impls. Skill allowlist / sensitive HITL live only on `beforeTool` — `execTurn` does not re-check.

## Rules

- A hook **decides** and may **rewrite ctx**. The loop **executes** (LLM, `execTurn(turn, ctx.toExecContext())`, HITL, `emit`).
- Cross-turn capability changes go on **`agent.*`**. Filtering `ctx.tools` / `ctx.skills` lasts one turn (`syncFromAgent` recopies).
- Hooks are sync aside from data already on `ctx`. No nested `chatCompletion`.
- Visibility: interventions write `RecoveryPlan` and/or ledger `#hint` / `#compact` / `#constraint`.
- `allow` from a hook does not bypass skill allowlist / sensitive HITL / privacy flags — those stock hooks still run first.

## Explicitly out of scope

- Cordis plugins, `next()` onion, profiles/bundles.
- MAF three-layer middleware classes.
- Compaction as a side effect inside `compileUserPrompt`. Compile formats `ctx.messages` only.
