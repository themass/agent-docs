# Pi 源码索引：按问题找文件

> 这是面向源码阅读的导航，不是把每个文件逐行重述。版本基线：官方 `v1.3.0` / commit `71023aec1546d6d677a65669c5665c0927ce0dd0`，2026-10-17 核验。源码链接固定到发布标签，不再默认跳到本地旧 checkout；版本差异见 [VERSION_ALIGNMENT.md](./VERSION_ALIGNMENT.md)。

## 1. 模块边界总表

| 想回答的问题 | 先读 | 再读 |
|---|---|---|
| Agent 为什么会继续请求 | `packages/agent/src/agent-loop.ts` `runLoop` | `packages/agent/test/agent-loop.test.ts` |
| 工具为什么并行/串行 | `agent-loop.ts` `executeToolCalls` | `agent/src/types.ts` `AgentTool.executionMode` |
| 模型实际看到什么 | `coding-agent/src/core/agent-session.ts` `_installAgentRequestProjection` | `session-manager.ts`, `ai/src/utils/transcript.ts` |
| Prompt 如何增量更新 | `coding-agent/src/core/system-prompt.ts` | `agent-session.ts` `_preparePromptAndToolLoadout` |
| 会话如何分支和恢复 | `coding-agent/src/core/session-manager.ts` | `core/messages.ts`, `agent-session-tree-navigation.test.ts` |
| 自动压缩如何决定切点 | `coding-agent/src/core/compaction/` | `agent-session.ts` `_checkCompaction` |
| Provider 如何统一 | `ai/src/models.ts` | `ai/src/api/`, `ai/src/providers/`, `ai/src/auth/` |
| MCP 如何接工具 | `mcp/src/client.ts` | `coding-agent/src/extensions/mcp/` |
| Code Mode 如何限制脚本 | `codemode/src/runtime/` | `coding-agent/src/extensions/codemode/` |
| Durable 任务如何恢复 | `durable/src/harness/scheduler.ts` | `durable/src/types.ts`, `registry.ts` |
| Durable 模型请求如何分 phase | `durable/src/harness/generation.ts` | `compaction.ts`, `tool.ts` |
| Durable 上下文如何生成 | `durable/src/harness/context.ts` | `entries.ts`, `documents.ts` |
| JSONL 后端如何提交 | `durable/src/storage/jsonl/storage.ts` | `storage/memory.ts` |
| SQLite 后端如何提交 | `durable/src/storage/sqlite/storage.ts` | `sqlite/migrations.ts`, runtime adapters |
| 跨进程 state/RPC 如何工作 | `chord/src/host.ts`, `contract.ts` | `state.ts`, `delta/`, `link.ts` |
| SSH 远程执行如何恢复连接 | `env/src/connection.ts` | `env/src/remote-env.ts`, `daemon/src/frame.rs` |
| 项目资源什么时候可信 | `coding-agent/src/core/trust-manager.ts` | `project-trust.ts`, `resource-loader.ts` |
| 扩展如何影响一轮请求 | `coding-agent/src/core/extensions/runner.ts` | `extensions/types.ts`, `agent-session.ts` |
| 终端 UI 如何渲染 | `tui/src/tui.ts` | `tui/src/layout.ts`, `components/`, `terminal-image.ts` |

## 2. Agent Core 精确阅读顺序

```text
packages/agent/src/types.ts
  AgentMessage / AgentContext / AgentEvent / AgentLoopConfig / AgentTool
      ↓
packages/agent/src/agent-loop.ts
  agentLoop → runAgentLoop → runLoop → streamAssistantResponse
      ↓
packages/agent/src/agent.ts
  state reducer、pending queues、prompt/continue、事件订阅
      ↓
packages/agent/src/proxy.ts
  代理/包装不同 Agent 实例时的边界
```

`agent-loop.ts` 里的 `streamAssistantResponse` 是消息变换的最后一道边界：

```text
AgentMessage[]
  -- transformContext --> AgentMessage[]
  -- convertToLlm --> Message[]
  -- normalizeContext --> LLM Context
  -- streamFn --> AssistantMessageEvent stream
```

## 3. Coding Agent 精确阅读顺序

```text
src/main.ts / cli.ts
  -> core/sdk.ts
  -> core/agent-session-runtime.ts
  -> core/agent-session-services.ts
  -> core/agent-session.ts
      -> settings / model-runtime / resource-loader / extensions / tools
      -> agent-core
  -> core/session-manager.ts
  -> modes/{print-mode,json-event}.ts 或 rpc-entry.ts
```

常见的“入口错觉”：

- `sdk.ts` 创建 Agent 和 AgentSession，但不是每个模式都从同一个 UI 入口进入。
- `AgentSession.prompt()` 先处理 extension command（`/foo`），再处理 input handlers、skill/template expansion，最后才进入 Agent run。
- Agent event 的 `_handleAgentEvent()` 先给 extension，再给 public listeners，然后在 `message_end` 处持久化；因此“监听到消息”和“写入 session”的相对顺序是有设计的。

## 4. Durable 精确阅读顺序

```text
src/types.ts
  TaskState / TaskDefinition / TaskRuntime / Storage / DocumentRecord
      ↓
src/session/session.ts + transaction.ts
  mutation line / committed publication / failure guard
      ↓
src/storage/memory.ts
  reference commit semantics
      ↓
src/storage/jsonl/storage.ts 或 storage/sqlite/storage.ts
  physical backend
      ↓
src/harness/harness.ts
  Conversation facade + TaskScheduler wiring
      ↓
src/harness/scheduler.ts
  reserve / running / waiting / abort cascade / recovery
      ↓
src/harness/registry.ts
  built-in tasks: GenerationTask / ToolTask / CompactionTask
      ↓
src/harness/generation.ts + tool.ts + compaction.ts
  concrete phase machines
```

## 5. Durable 的三个版本面

| 版本面 | 位置 | 影响 |
|---|---|---|
| npm/workspace package | `packages/*/package.json` | 安装和依赖解析 |
| task definition | `TaskDefinition.version` | input/checkpoint migration |
| storage schema | `FORMAT_VERSION` 或 SQLite migrations | 物理数据读取/升级 |

调试恢复问题时必须记录三者，不能只说“Pi 版本”。

## 6. 关键测试映射

| 子系统 | 测试 |
|---|---|
| Agent loop | `packages/agent/test/agent-loop.test.ts`, `agent.test.ts` |
| CLI session | `packages/coding-agent/test/agent-session-*.test.ts`, `session-*.test.ts` |
| compaction | `coding-agent/test/agent-session-auto-compaction-queue.test.ts` |
| Durable generation/tool | `durable/test/harness-generation.test.ts`, `harness-nested-tools.test.ts` |
| Durable recovery | `durable/test/session-checkpoints-migrations.test.ts` |
| Durable backends | `durable/test/jsonl-storage.test.ts`, `sqlite-migrations.test.ts` |
| Chord | `chord/test/replicated-state.test.ts`, `reload.test.ts`, `requests.test.ts` |
| Code Mode | `codemode/test/worker-lifetime.test.ts`, `portable.test.ts` |
| MCP | `mcp/test/client.test.ts`, `streamable-http.test.ts`, `oauth.test.ts` |
| Remote env | `env/test/conformance.test.ts`, `remote.test.ts`, `terminal.test.ts` |
| TUI | `tui/test/editor.test.ts`, `tui-alt-screen.test.ts`, `markdown.test.ts` |

## 7. 本次核对的边界

已按本地源码核对：11 个 workspace 包、`packages/*/src` 主要入口、coding-agent core/extensions、Durable harness/session/storage/env、MCP、Code Mode、Chord 和测试目录。

未在本轮逐一核验：外部第三方 Pi 插件的最新仓库实现、Pi-chat/Prime 等上层产品、Provider 每一个单独 adapter 的全部请求字段。涉及这些内容时应在相应仓库和 commit 上另做证据链，不要把生态文档当作 core 源码事实。

## 8. 本地源码目录清点：避免再次遗漏整包

下表按官方 v1.3.0 重新清点 `packages/*/src` 的全部一级目录和一级文件。文件数含 `.d.ts`、生成代码及目录内 JSON/原生资源，因此与仅统计 TS 的旧表口径不同；它证明文件存在，不表示每个文件都已逐行分析。`env/daemon/src` 是另一个 Rust 实现入口，另行列出。

| 包 | src 下文件数（含资源） | 一级子目录 | 一级文件入口 |
|---|---:|---|---|
| agent | 6 | — | [agent-loop.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/agent-loop.ts), [agent.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/agent.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/index.ts), [proxy.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/proxy.ts), [stream-fn.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/stream-fn.ts), [types.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/agent/src/types.ts) |
| ai | 199 | [api/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/ai/src/api), [auth/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/ai/src/auth), [compat/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/ai/src/compat), [providers/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/ai/src/providers), [utils/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/ai/src/utils) | [bedrock-provider.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/bedrock-provider.ts), [bun-oauth.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/bun-oauth.ts), [cli.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/cli.ts), [compat.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/compat.ts), [env-api-keys.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/env-api-keys.ts), [image-models.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/image-models.ts), [images-api-registry.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/images-api-registry.ts), [images.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/images.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/index.ts), [legacy-api-aliases.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/legacy-api-aliases.ts), [model-catalog.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/model-catalog.ts), [models-store.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/models-store.ts), [models.generated.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/models.generated.ts), [models.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/models.ts), [oauth.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/oauth.ts), [session-resources.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/session-resources.ts), [types.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/ai/src/types.ts) |
| chord | 32 | [context/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/chord/src/context), [delta/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/chord/src/delta) | [cell.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/cell.ts), [cluster.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/cluster.ts), [connection.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/connection.ts), [contract.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/contract.ts), [declare.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/declare.ts), [errors.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/errors.ts), [host.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/host.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/index.ts), [json.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/json.ts), [link.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/link.ts), [loader.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/loader.ts), [manager.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/manager.ts), [node.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/node.ts), [object.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/object.ts), [output.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/output.ts), [publish.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/publish.ts), [registry.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/registry.ts), [reload.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/reload.ts), [remote.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/remote.ts), [schema.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/schema.ts), [state.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/state.ts), [types.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/types.ts), [websocket.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/websocket.ts), [wire.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/chord/src/wire.ts) |
| codemode | 17 | [runtime/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/codemode/src/runtime) | [cloudflare-modules.d.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/cloudflare-modules.d.ts), [cloudflare.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/cloudflare.ts), [declarations.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/declarations.ts), [identifier.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/identifier.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/index.ts), [portable.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/portable.ts), [source.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/source.ts), [types.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/types.ts), [wasm.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/codemode/src/wasm.ts) |
| coding-agent | 262 | [bun/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/bun), [cli/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/cli), [core/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/core), [experimental/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/experimental), [extensions/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/extensions), [modes/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/modes), [utils/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/coding-agent/src/utils) | [cli.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/cli.ts), [config.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/config.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/index.ts), [main.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/main.ts), [migrations.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/migrations.ts), [package-manager-cli.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/package-manager-cli.ts), [rpc-entry.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/coding-agent/src/rpc-entry.ts) |
| durable | 82 | [codemode/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/codemode), [env/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/env), [harness/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/harness), [images/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/images), [session/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/session), [storage/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/storage), [testing/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/testing), [tool-search/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/tool-search), [tools/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/durable/src/tools) | [documents.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/documents.ts), [entries.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/entries.ts), [errors.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/errors.ts), [ids.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/ids.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/index.ts), [search.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/search.ts), [tasks.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/tasks.ts), [truncate.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/truncate.ts), [types.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/durable/src/types.ts) |
| env | 8 | — | [connection.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/connection.ts), [errors.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/errors.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/index.ts), [list-files.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/list-files.ts), [remote-env.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/remote-env.ts), [ssh.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/ssh.ts), [terminal.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/terminal.ts), [watch.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/env/src/watch.ts) |
| evals | 5 | — | [cli.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/evals/src/cli.ts), [docker.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/evals/src/docker.ts), [harness.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/evals/src/harness.ts), [plan.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/evals/src/plan.ts), [report.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/evals/src/report.ts) |
| mcp | 18 | [oauth/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/mcp/src/oauth), [protocol/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/mcp/src/protocol), [testing/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/mcp/src/testing), [transports/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/mcp/src/transports) | [auth-provider.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/mcp/src/auth-provider.ts), [client.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/mcp/src/client.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/mcp/src/index.ts) |
| telemetry | 6 | [testing/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/telemetry/src/testing) | [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/telemetry/src/index.ts), [memory.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/telemetry/src/memory.ts), [noop.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/telemetry/src/noop.ts) |
| tui | 46 | [components/](https://github.com/earendil-works/pi/tree/v1.3.0/packages/tui/src/components) | [alt-screen-search.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/alt-screen-search.ts), [autocomplete.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/autocomplete.ts), [colors.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/colors.ts), [editor-component.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/editor-component.ts), [fuzzy.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/fuzzy.ts), [index.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/index.ts), [keybindings.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/keybindings.ts), [keys.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/keys.ts), [kill-ring.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/kill-ring.ts), [latex.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/latex.ts), [layout-node.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/layout-node.ts), [layout.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/layout.ts), [native-modifiers.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/native-modifiers.ts), [native-module-path.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/native-module-path.ts), [native-platform.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/native-platform.ts), [oklab.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/oklab.ts), [program-status.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/program-status.ts), [stdin-buffer.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/stdin-buffer.ts), [terminal-colors.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/terminal-colors.ts), [terminal-image.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/terminal-image.ts), [terminal.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/terminal.ts), [tui-alt-screen.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/tui-alt-screen.ts), [tui-main-screen.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/tui-main-screen.ts), [tui.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/tui.ts), [undo-stack.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/undo-stack.ts), [utils.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/utils.ts), [wheel-scroll.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/wheel-scroll.ts), [word-navigation.ts](https://github.com/earendil-works/pi/blob/v1.3.0/packages/tui/src/word-navigation.ts) |

补充：[env Rust daemon](https://github.com/earendil-works/pi/tree/v1.3.0/packages/env/daemon/src)。各包 `test/`、scripts、examples 和生成工具不计入上面的 src 数量。完整逐文件讲解仍是后续深化任务。
