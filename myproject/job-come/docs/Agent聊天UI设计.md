# JobCome Agent 聊天 UI 与 Context 设计

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 状态 | M1 冻结候选 |
| 关联 | [前端架构与鉴权.md](前端架构与鉴权.md) · [Prompt与Skill设计.md](Prompt与Skill设计.md) · [可观测性与Trace.md](可观测性与Trace.md) |

对齐参考：**Cursor Composer** 输入区 + **Context Usage** 面板（调试用）。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **模型不对用户暴露** | 用户不选 `mt-deepseek-v4-pro`；只显示模式（简历教练 / 模拟面） |
| **输入区对齐 Cursor** | 底部大圆角 Composer、左侧 `+`、右侧发送；视觉与交互一致 |
| **Context Usage 可关** | 默认关闭；`JOB_COME_DEBUG_CONTEXT_USAGE=true` 或开发者开关打开 |
| **Wire 用 JSON，代码用对象** | SSE 帧是 JSON；前后端内部用 Pydantic / TypeScript 类型 |

---

## 2. Composer 输入区（对齐 Cursor）

### 2.1 布局

```text
┌─────────────────────────────────────────────────────────────────┐
│  （消息列表在上，略）                                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  帮我把第二段经历改得更量化…                                  │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│  [+]  简历教练 · 已登录          [Context 86% ▾]    [🎤]  [↑]   │
└─────────────────────────────────────────────────────────────────┘
```

| 元素 | 行为 |
|------|------|
| 多行输入 | `Enter` 发送，`Shift+Enter` 换行；自动增高，最大 8 行 |
| **`+`** | 附件（M1：关联当前 Profile/JD；M2：上传补充材料） |
| **模式标签** | `简历教练` / `模拟面试` / `记真题` — 非模型名 |
| **Context %** | 仅 debug 开时显示；点击展开 Usage 面板 |
| **麦克风** | M2 LiveKit；M1 隐藏或 disabled |
| **发送 ↑** | 有内容时可点；流式中变停止 |

### 2.2 组件路径

```text
apps/web/components/agent/
├── AgentComposer.tsx          # 输入区容器
├── AgentMessageList.tsx
├── ContextUsagePanel.tsx      # 图二弹层
├── ContextUsageBar.tsx          # 顶部分段进度条
└── useAgentStream.ts          # SSE → 强类型事件
```

### 2.3 与 Cursor 差异（刻意）

| Cursor | JobCome |
|--------|---------|
| 用户选模型 Composer 2.5 | **不选模型**；后端 Skill 决定 LiteLLM 别名 |
| 通用代码助手 | 简历/面试域；左侧 ProfileEditor 同步 |
| Context 常开 | **默认关**，调试开 |

---

## 3. Context Usage 面板

### 3.1 展示内容（对齐图二）

| 桶（bucket） | 颜色 | 来源 |
|--------------|------|------|
| `system_prompt` | 灰 | DeerFlow 平台 system + Skill 激活全文 |
| `tool_definitions` | 紫 | MCP `jobcome_*` + DeerFlow 内置 tools schema |
| `rules` | 绿 | `.cursor/rules` 等价物 → JobCome `AGENTS.md` / 产品规则注入 |
| `skills` | 棕 | `<skill_system>` 索引（未激活的 skill 摘要） |
| `mcp_dynamic` | 紫红 | 当轮实际绑定的 tool 子集 |
| `subagent` | 蓝 | `task` 子 Agent 额外 system |
| `summarized` | 深红 | 压缩后的历史摘要 |
| `conversation` | 橙 | 多轮 user/assistant 消息 |

顶部：`{percent}% Full` · `~{used} / {limit} Tokens`

### 3.2 开关

| 环境 | 默认 |
|------|------|
| `JOB_COME_ENV=development` | 开（或 `.env` `JOB_COME_DEBUG_CONTEXT_USAGE=true`） |
| `production` | **关**；API 不返回 `context_usage` 帧 |

前端：

```typescript
const showContext = process.env.NEXT_PUBLIC_DEBUG_CONTEXT_USAGE === 'true'
```

用户设置里可隐藏「开发者选项」（M2）。

---

## 4. Token 组成：算在哪里？

### 4.1 结论（冻结）

| 职责 | 放哪里 | 原因 |
|------|--------|------|
| **分桶统计（UI 用）** | **DeerFlow 组装消息后** · JobCome `DeerFlowSessionClient` 适配层 | 只有这里知道 system / skill / tools / history 各有多少 |
| **实际计费 tokens** | **LiteLLM 响应** `usage` | 厂商最终口径 |
| **成本/链路追踪** | **LiteLLM → Langfuse** hook | 生产观测，不给终端用户 |
| **不在 LiteLLM hook 做 UI 分桶** | — | LiteLLM 只见最终 `messages[]`，不知道 skill 索引 vs 全文 |

```text
DeerFlow 组装 messages[]
        │
        ▼
JobCome adapter.tokenize_context(buckets)   ← UI 分桶（tiktoken / litellm.token_counter）
        │
        ├──► SSE event: context_usage { buckets, total, limit, estimated: true }
        │
        ▼
DeerFlow → LiteLLM (jobcome-coach 等别名)
        │
        ▼
Response usage { prompt_tokens, completion_tokens }  ← 写回 context_usage.actual
        │
        └──► Langfuse（LiteLLM callback，生产）
```

### 4.2 为何不是 LiteLLM hook？

LiteLLM `success_callback` 收到的是**单次 completion** 的扁平 `usage`，没有：

- 哪一段是 tool schema
- 哪一段是未激活 skill 索引
- 哪一段是压缩摘要

这些是 **DeerFlow harness** 在调用 LLM 之前的上下文构建逻辑，必须在 **DeerFlow 侧或 JobCome 包装 DeerFlow 的 adapter** 里拆。

### 4.3 实现落点

```text
libs/agentkit/adapters/deerflow/
  client.py              # stream() 转发事件
  context_usage.py       # ContextUsageBuilder + token_counter

job-come/src/jobcome/services/
  resume_agent_service.py   # SSE 统一事件格式
```

**SSE 事件示例：**

```json
{
  "type": "context_usage",
  "data": {
    "percent": 86,
    "used_tokens": 172000,
    "limit_tokens": 200000,
    "estimated": true,
    "buckets": [
      { "id": "system_prompt", "tokens": 531 },
      { "id": "tool_definitions", "tokens": 9800 },
      { "id": "conversation", "tokens": 148900 }
    ],
    "actual": { "prompt_tokens": 171240, "completion_tokens": 820 }
  }
}
```

`estimated: true` 表示分桶为本地 tokenizer；`actual` 在 turn 结束后由 LiteLLM usage 回填。

### 4.4 上下文上限

| 项 | M1 默认 |
|----|---------|
| `limit_tokens` | 200K（与图二一致；可按模型配置表） |
| 超限策略 | DeerFlow compaction 先摘要；仍超则 UI 警告 + 建议新开 session |

---

## 5. LiteLLM 返回值：对象还是 JSON？

| 层级 | 形态 | 说明 |
|------|------|------|
| LiteLLM Proxy HTTP | **JSON** | OpenAI 兼容 `chat.completion` JSON |
| Python `litellm.completion()` | **对象** `ModelResponse` | 最佳实践：业务代码用对象 |
| LangChain / DeerFlow 内部 | **Message 对象** | 不手写 dict |
| JobCome Service | **Pydantic 模型** | `AgentStreamEvent`, `ContextUsage` |
| 浏览器 SSE | **JSON 行** | `data: {...}\n\n`；前端 parse 后变 TS 类型 |

**冻结：边界序列化，内部一律对象。**

```python
# ✅ Service 层
event = ContextUsageEvent(data=usage_model)
yield f"data: {event.model_dump_json()}\n\n"

# ❌ 不要在业务里 json.loads 来回转
```

---

## 6. 非 Agent 调用的 LLM（无 Context 面板）

| 场景 | 调用链 | UI |
|------|--------|-----|
| 简历解析结构化 | `ProfileIngestService` → LiteLLM `jobcome-fast` | 无 Composer；仅进度条 |
| 拔高单次 Writer | `POST /elevate` → DeerFlow task 或直连 | 预览区，无分桶面板 |
| Agent 多轮对话 | DeerFlow session SSE | **有 Composer + Context（debug）** |

---

## 7. 相关配置

```bash
# .env
JOB_COME_DEBUG_CONTEXT_USAGE=true   # 开发默认 true，生产 false
JOB_COME_CONTEXT_TOKEN_LIMIT=200000
```

```bash
# apps/web/.env.local
NEXT_PUBLIC_DEBUG_CONTEXT_USAGE=true
```

---

## 8. 实现顺序

| 周 | 交付 |
|----|------|
| W1 | `AgentComposer` 静态 UI + mock SSE |
| W2 | DeerFlow SSE 接通 + `message_delta` |
| W2.5 | `ContextUsageBuilder` + debug 开关 |
| W3 | Langfuse 对照 actual vs estimated |
