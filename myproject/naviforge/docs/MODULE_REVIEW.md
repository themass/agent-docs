# MVP 模块边界审查（2026-08-10）

> 包级结论仍成立。循环、审计信封、工作集、子 Agent 的**当前设计**以 [AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)（2026-08-13）为准。结构债在 `runtime/agent.ts` 与 extension 胶水，不在再拆 package。

## 结论

当前拆分**总体合理，适合继续迭代**；没有需要立刻合并或再拆的新 package。

```text
extension ──→ runtime ──→ dom-plane
    │             ├──→ network-plane
    │             └──→ shared
    ├──→ skill-runtime
    └──→ playbook ──→ dom-plane / network-plane
    ⇅
localhost Host ──→ MCP Server / external MCP Clients
```

## 各模块职责

| 模块 | 状态 | 边界判断 |
|------|------|----------|
| `shared` | 类型、schema、`ToolResult` | 正确。已删掉未使用且会过期的页面消息类型。 |
| `dom-plane` | 浏览器 DOM 抽象 | 正确。Chrome 消息和 content-script 实现在 `extension`，没有倒灌 Chrome API。 |
| `network-plane` | Network 事件模型、过滤、wait 条件 | 正确。CDP 监听留在 `extension`，核心包不依赖 Chrome。 |
| `runtime` | Agent loop、Prompt、LLM、动作记录 | 正确。只通过 Plane 接口操作浏览器。 |
| `skill-runtime` | Skill 模型、路由、低信任 prompt 格式 | 现在略小，但保留合理；安装/签名/权限将在后续使用这里。 |
| `playbook` | AST、参数化、Forge、确定性 Runner | 正确。已直接依赖两个 Plane 接口，因为重放本来就是跨平面行为。 |
| `apps/extension` | MV3、Chrome API、Side Panel、本地存储 | 正确。它是唯一平台适配层，短期可以包含 UI 与 `chrome.storage`。 |
| `apps/host` | 本地认证桥、stdio MCP Server、外部 MCP Client | 正确。Node/子进程能力没有泄漏进 MV3 核心；云端不是运行时依赖。 |

## 已消除的重复

- 删除 `shared` 中没有消费者的 `PageControlMessage` / `PageControlAction`；
- 删除 Playbook 的废弃 `draftPlaybook`；
- Playbook 的 selector/变量/Network wait 都收敛到一个 AST，不在 UI 和 runtime 各维护一份。

## 有意保留的临时边界

1. `PageController.selectorMap` 不是 page-agent 公共 API。当前通过受限适配访问它以生成 selector；若上游变更，功能会降级为 index fallback。**下一次 page-agent 升级前必须回归测试。**
2. DOM action 与 Network 事件只按固定 250 ms 窗口关联，不能证明因果。它只生成可选 `network_wait`，不是安全或业务关键断言。后续 Host/CDP 版本可用 initiator/correlation ID 升级。
3. `skill-runtime` 只执行低信任 Instruction Skills；本地导入不会执行 JavaScript。外部工具统一通过 Host MCP Client 和工具白名单进入 Agent。

## 不应现在做的拆分

- 不拆 `prompt-compiler`：它与 Agent loop 仍共同频繁变化；
- 不拆 `ui`：当前只有 Side Panel 一个消费者；
- 不拆 `mcp-bridge` package：当前只有 Host 一个协议消费者，拆包会形成转发层；
- 不建 Cloud：本地运行不依赖云端，保持以后可替换的同步/控制面边界。

## 下一步推荐

1. 将 `network_wait` 的锻造改为用户可审阅的候选步骤；
2. 为 Playbook 添加 DOM 成功断言；
3. 为外部 MCP 的写工具增加逐次确认策略；`runtime` 继续只依赖回调接口，不依赖 Node MCP SDK。
