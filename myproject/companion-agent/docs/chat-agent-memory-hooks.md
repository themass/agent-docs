# 记忆 Hook 设计：插槽与召回组件

版本：草案 v1
状态：设计，未实现
范围：回合前召回、回合后写入的 hook 插槽与组件契约。**不涉及**具体记忆后端、向量或模型选型（那些由 `docs/chat-agent-memory-spec.md` 的存储端口规定），也不涉及具体业务（角色、人设、禁止清单的内容）。

## 1. 目标与边界

记忆子系统要满足三个要求：

1. **可替换**：召回的来源（记忆库、时间线、将来的别的东西）和写入的去向，都通过 hook 接入。换来源、加来源、去掉来源，不改回合主流程。
2. **与业务无关**：hook 层不认识「角色」「用户档案」「禁止清单」之类的概念。它只认通用的文本条目、来源、时间、分数。
3. **与插件无关**：hook 只依赖本文定义的协议，不依赖任何具体库。具体库只出现在适配器里。

不在本设计内：存储后端（见存储端口规范）、提取用的提示词与模型调用、禁止清单的内容、向量检索。

## 2. 分层

```
memory/hooks.py     协议与数据类（纯，无 IO）
memory/pipeline.py  编排：扇出召回、合并、预算裁剪、超时隔离（纯逻辑）
memory/...             具体的抽取服务（需要 LLM 调用时在这里）
memory/...        把存储端口适配成召回源 / 写入汇
bootstrap/...              按配置组装 hook 列表（唯一的组合根）
```

层级约束沿用现有 import-linter 契约：`domain` 不依赖 `adapters`；hook 协议只在 `domain`；只有 `bootstrap` 知道具体适配器。

## 3. 数据模型（与业务无关）

```python
@dataclass(frozen=True, slots=True)
class RecallQuery:
    user_id: str            # 不透明标识，hook 不解析其结构
    scope: str              # 调用方给的隔离范围（如应用名），hook 原样透传
    text: str               # 本轮用户输入，用于相关性
    occurred_before: datetime | None   # 只召回这个时间点之前的内容（回放/重试用）
    limit: int              # 每个来源的条数上限
    budget_chars: int       # 本次召回能占用的总字符数（见 §6）

@dataclass(frozen=True, slots=True)
class RecalledItem:
    text: str               # 已可直接放进提示词的一句话
    source: str             # 来源名，如 "facts"、"timeline"；用于溯源与去重
    ref: str                # 来源内的稳定标识，用于去重与删除
    occurred_at: datetime | None
    score: float | None     # 来源给出的相关性，无则 None；不跨来源比较
    tags: frozenset[str]    # 通用标签，如 "fact"、"event"，渲染时用于分段

@dataclass(frozen=True, slots=True)
class RecallResult:
    items: tuple[RecalledItem, ...]
    source: str             # 产出它的 hook 名
    truncated: bool         # 来源内部是否因为 limit 截断
    error: str | None       # 失败原因；失败时 items 为空，不抛出

@dataclass(frozen=True, slots=True)
class TurnRecord:
    scope: str
    user_id: str
    turn_id: str            # 幂等键：同一回合重放不应重复写入
    user_text: str          # 只给用户的话
    assistant_text: str     # 仅作消歧上下文，写入侧不得把它当作用户信息
    occurred_at: datetime
```

`text` 字段是召回的唯一输出形态：召回组件负责把来源自己的结构渲染成一句话。渲染规则不在编排层，编排层只拼接。

## 4. 插槽

回合生命周期里有三个插槽，外加一个删除传播插槽。

| 插槽 | 时机 | 协议 | 失败语义 |
|---|---|---|---|
| `recall` | 回合前，主脑调用之前 | `Recaller` | 单个来源失败只记 `RecallResult.error`，其余来源照常 |
| `render` | 召回之后，拼进提示词之前 | `RecallRenderer`（可选，默认按 `tags` 分段） | 渲染失败回退为纯文本拼接 |
| `record` | 回合结束之后，异步 | `Recorder` | 失败只记日志，不影响已返回的回合 |
| `forget` | 用户删除某条或全部记忆时 | `Forgetter` | 失败进入重试队列，不阻塞删除请求的响应 |

### 4.1 Recaller

```python
class Recaller(Protocol):
    name: str
    async def recall(self, query: RecallQuery) -> RecallResult: ...
```

约定：
- 实现**不得抛出**异常；失败通过 `RecallResult.error` 返回。
- 实现必须尊重 `query.limit` 与 `query.occurred_before`。
- 实现必须是幂等的读操作，不得写入。

### 4.2 Recorder

```python
class Recorder(Protocol):
    name: str
    async def record(self, turn: TurnRecord) -> RecordOutcome: ...
```

约定：
- 同一个 `turn_id` 多次调用，结果等同于调用一次（幂等）。
- `assistant_text` 只用于消歧，实现不得把它的内容原样写成用户事实（这是提取侧的规则，写在这里是为了让任何 Recorder 都遵守）。
- `RecordOutcome` 报告写入了几条、跳过了几条、失败原因；不抛出。

### 4.3 Forgetter

```python
class Forgetter(Protocol):
    name: str
    async def forget(self, scope: str, user_id: str, ref: str | None) -> int: ...
```

`ref=None` 表示删除该用户在该 scope 下的全部。返回删除条数。

## 5. 编排规则

这些规则放在 `memory/pipeline.py`，与具体组件无关，所有组件都遵守。

1. **扇出**：`recall` 插槽里的所有 `Recaller` 并发执行，互不等待。
2. **超时隔离**：每个 `Recaller` 有独立超时（默认 800 ms，可按来源配置）。超时视为该来源失败，`error="timeout"`。整个回合的召回阶段有总上限，超过则直接用已到达的结果。
3. **合并**：按 `(source, ref)` 去重；同一 `ref` 保留先到达的那条。
4. **排序**：先按 `occurred_at` 降序（缺失的排最后），再按 `score` 降序（`None` 排最后）。**不跨来源比较 `score`**——每个来源的分数含义不同。
5. **预算裁剪**：按排序顺序累加 `len(text)`，超过 `budget_chars` 即停止。被裁掉的不计入任何结果，`truncated` 置位。
6. **空结果不是错误**：没有召回到东西，提示词里对应段落省略，不写占位文字。
7. **审计**：每次召回记录各来源的耗时、条数、错误，供排查；不记录 `text` 原文（隐私）。

## 6. 预算与降级

- 预算单位是**字符**，不是 token。字符与 token 的换算属于模型适配层，hook 层不知道模型。
- 召回失败不是回合失败。最坏情况是这一轮没有记忆，回复仍然产出。
- 写入失败不是回合失败。最坏情况是这一轮的内容没有被记住，下一轮可以补（依赖 `turn_id` 幂等，允许重试）。

## 7. 配置

组装在 `bootstrap` 完成，hook 列表由配置声明，顺序即优先级。

```toml
[memory.recall]
budget_chars = 1200
timeout_ms = 800

[[memory.recall.sources]]
name = "facts"
adapter = "memory_port"     # 适配器名，由 bootstrap 注册表解析
limit = 8

[[memory.recall.sources]]
name = "timeline"
adapter = "timeline"
limit = 5

[[memory.record.sinks]]
name = "facts"
adapter = "memory_port"
```

配置只声明「用哪些适配器、各自参数」，不声明业务规则。增加一个来源 = 实现一个适配器 + 在注册表登记 + 配置里加一段。编排层与主流程不改。

## 8. 与现有代码的对应

| 现状 | 问题 | 本设计的归宿 |
|---|---|---|
| `MemoryRecallMiddleware` 直接调 `memory.search` 与 `timeline.list_for_user` | 来源写死；两者的返回结构不同，各自渲染 | 两者都变成 `Recaller` 适配器；渲染进各自的适配器 |
| `EventExtractionMiddleware` 写时间线；`memory/extraction.py` 写记忆端口 | 两条写入路径，重复的提取逻辑 | 两者都变成 `Recorder`；是否合并为一次提取由 §9 问题 2 决定 |
| `_render` 在 `domain/text/render.py` | 渲染与来源耦合 | 渲染由 `RecalledItem.tags` 驱动，来源不再关心段落结构 |
| 删除只针对记忆端口 | 时间线里的事件删不掉 | `Forgetter` 插槽统一传播删除 |

中间件链的位置不变：安全在前，记忆与抽取在安全之后、成本之前。变化的只是记忆两端由 hook 列表驱动。

## 9. 待决定的问题

1. **【已决定】时间线是记忆的一个召回源。** 它与记忆端口同为「可召回的文本条目」，区别只在存储与来源标签，统一由 `Recaller` 协议接入，不另设协议。
2. **写入侧是否合并为一次提取？** 现在时间线事件与记忆事实各提取一次，成本翻倍，且结果可能不一致。建议合并为一次提取、多个 `Recorder` 分别落库。这涉及提示词，需要单独确认。
3. **`occurred_before` 是否需要？** 只在回放与重试场景有用。如果回放不做，可以删掉以简化契约。

## 10. 一致性检查

沿用 `tests/memory_conformance.py` 的思路，为 hook 增加两个检查集（实现时再写）：

- `check_recaller(recaller)`：不抛异常；尊重 `limit`；`occurred_before` 之后的内容不出现；多次调用结果一致（只读）。
- `check_recorder(recorder)`：同一 `turn_id` 重复调用不产生重复条目；失败不抛出；`assistant_text` 的内容不会成为独立事实（用可构造的样例验证）。

编排层另有单元测试：超时隔离、去重、跨来源不比较分数、预算裁剪的边界。

## 11. 接入方式

记忆以**进程内库**的形式提供，所有 agent 直接依赖同一套协议。HTTP 与 MCP 是对外的两个可选出口，不是 agent 之间的主通道。

### 11.1 三个调用方的接法

| 调用方 | 运行入口 | 接入方式 | 召回触发 |
|---|---|---|---|
| 浅聊（companion） | 回合链 `MiddlewareChain` + DeerFlow 图 | 回合链中的召回中间件、写入中间件，调用编排层 | 每回合必定 |
| job agent（job-come，DeerFlow 嵌入式 client） | `DeerFlowClient` 子类，覆盖 `_get_tools` / `_get_runnable_config` | 运行前在 `_get_runnable_config` 或启动处调用 `recall`，运行后调用 `record` | 每次运行必定 |
| 将来的其他 agent | 视运行时而定 | 同上：在入口处调用编排层两次 | 按运行时决定 |

**中间件不是设计本身，而是编排层的一种调用点。** 编排层只暴露两个入口：

```python
await pipeline.recall(query) -> list[RecalledItem]    # 回合前
await pipeline.record(turn) -> None                   # 回合后，异步，不阻塞
```

每个 agent 在自己的运行入口里调用这两个函数。companion 用中间件调用它，是因为它本来就有回合链；job-come 没有回合链，就在运行入口调用。

### 11.2 按需召回的工具（可选，补充）

当 agent 需要「按需查」而不是「每次都查」时，额外注册一个工具包装 `recall`。工具的结果是不可信输入（见 T §3.4），渲染时仍走 `tags` 分段，不把原文当指令。

工具与每回合召回并存时，以每回合召回为准，工具只补充查询。

### 11.3 HTTP 与 MCP 的位置

- **HTTP `/memory/*`**：给客户端（App）用，靠用户登录态鉴权。不作为 agent 之间的接口。
- **MCP**：只在两种情况下使用：
  1. 调用方不是 Python，或不想依赖库；
  2. 需要把记忆暴露给外部 agent 工具链。
  代价是每次调用多一跳，且 MCP 结果要按 T §3.4 做注入防护。同进程的 agent 不走 MCP。

### 11.4 隔离与身份

- 每个调用方通过 `hub.for_app(name)` 拿到作用域客户端。应用名由组合根注册，调用方不能自选。
- 隔离是 `app:uid` 复合键。**当前只有应用层隔离，没有令牌层隔离**：两个应用共享同一张表，任何能调用 `ScopedMemory` 的代码都能读写另一个应用的数据。这依赖调用方不伪造应用名，需要在代码评审和测试里守住（见 §10 的检查集）。
- 同一个用户在两个应用里是两份记忆。是否需要打通，是产品决定，不在本设计内。

### 11.5 失败语义

- 召回失败：回合照常进行，没有记忆段落。
- 写入失败：本轮内容不入库，依赖 `turn_id` 幂等，允许后续补写。
- 删除失败：进入重试队列，不阻塞用户的删除请求。

## 12. 不做的事（本阶段）

- 不实现任何具体适配器的新逻辑，现有适配器只需改为实现本协议。
- 不引入向量检索或任何模型依赖。
- 不改变中间件链的顺序与安全语义。
