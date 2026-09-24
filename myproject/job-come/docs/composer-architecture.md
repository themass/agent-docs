# Composer 架构说明

JobCome 的 Agent 输入区有两套实现，**默认用的是 legacy，不是 assistant-ui**。

## 当前默认：`AgentComposer`（legacy / naviforge 风格）

- 路径：`apps/web/components/agent/AgentComposer.tsx`
- 入口：`AgentComposerSwitch` → `AgentSidebar` / `AgentWorkbench`
- 能力：多行输入、附件、粘贴截图、**可拖动声纹弹层**、摄像头、Enter/Ctrl+Enter 队列
- 这是我们从 **naviforge** 移植并增强的实现，也是产品默认路径

## 保留但未启用：`@assistant-ui/react` 路径

以下文件**没有删除**，只是不再作为默认 composer：

| 文件 | 作用 |
|------|------|
| `AgentAssistantComposer.tsx` | assistant-ui `ComposerPrimitive` 封装 |
| `AgentAssistantThread.tsx` | assistant-ui 消息线程 |
| `providers/AssistantUiRuntimeProvider.tsx` | External store runtime |
| `providers/useJobComeExternalStore.ts` | 消息 ↔ thread 适配 |
| `assistant-ui/*` | Markdown、Tool parts |

### 为什么切回 legacy？

1. assistant-ui 路径需要 `AuiProvider`，曾导致生产/开发崩溃
2. legacy 已对齐 naviforge 的媒体能力（声纹、摄像头、附件）
3. 消息区使用自研 `AgentStreamPanel` + `AgentLoopCard`（Cursor 风格折叠），不依赖 assistant-ui thread

### 从 assistant-ui 保留的「最佳实践」

- **External store 模式**（`useJobComeExternalStore`）— 若将来重新启用 assistant-ui，消息状态仍可复用
- **ComposerPrimitive 布局参考** — 圆角卡片、底部工具栏、附件区结构
- **Markdown / Tool part 组件** — 可逐步迁回 thread 视图

### 清理策略（建议）

- **不删** `@assistant-ui/react` 依赖，直到明确放弃第二套 UI
- **可删**（需单独 PR）：仅当确认永远不用 assistant-ui composer/thread 时，再移除 `AgentAssistant*` 与 provider
- **当前建议**：保持代码隔离，默认 `composer-mode=legacy`，文档以本文件为准

## 相关配置

- `lib/composer-mode.ts` — 固定 `legacy`
- `hooks/useComposerMode.ts` — 始终返回 legacy
