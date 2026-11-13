# ADR-009：agent 回合的耗时由写 checkpoint 决定，不是模型

- **状态**：Accepted。已上线（`ad93edf`）。
- **日期**：2026-11-14
- **相关**：ADR-002（vendored DeerFlow）、`docs/architecture/TECH-AGENT.md`

## Context

用户反馈「大模型没有返回，太慢了，也不知道哪里慢」。前一轮排查给出过一个错误结论：认为
LangGraph 图缓存频繁失效（依据是日志里 615 次 `ListToolsRequest`）。实测证伪了这个判断——
同一线程 4 次 `_ensure_agent` 只有 1 次重建，缓存命中时重建耗时 0.01–0.03 秒。

真正的问题在别处，而且不在模型上。

### 实测数据

在生产机（`104.160.191.87`）上对真实回合打点，注册 checkpointer 的每次调用：

| 指标 | 修改前 | 修改后 |
|---|---|---|
| 单回合 checkpointer 往返 | **85 次**（55 次写） | **3 次** |
| 单次 `put` 中位耗时 | 361 ms | — |
| 单次 `put_writes` 中位耗时 | 536 ms | — |
| 单回合数据库耗时合计 | **约 25 秒** | 0.6 秒 |
| 单回合模型调用耗时 | 4.6–12.9 秒 | 4.6–12.9 秒（未变） |
| 预热后回合总耗时 | **16.5 秒** | **4.1–4.5 秒** |

关键事实：生产机到数据库 `newdb.sspacee.com` 的 **ping 是 169 ms**、TCP 建连 183 ms。
这是跨地域链路，不是内网。所以每次 checkpoint 往返都在付这 169 ms。

## 根因

LangGraph 默认 `durability="async"`：**每个图步骤**写一次 checkpoint，外加一组按 channel
的写记录。一个回合有 28 个步骤，于是 28 次 `put` + 27 次 `put_writes` + 2 次 `get_tuple`。

这不是 DeerFlow 的 bug，也不是缓存问题，而是一个默认值与部署拓扑的组合：
默认假设数据库在近处，而这里它在 169 ms 外。

## 决策

在 runnable config 上设 `durability="exit"`——整个 run 只在**图退出时**写一次。

```python
# jc/adapters/deerflow_harness_client.py
def jc_configurable_overrides() -> dict[str, Any]:
    return {"non_interactive": True, CONFIG_KEY_DURABILITY: settings.jc_deerflow_checkpoint_durability}
```

放在 config 里而不是 `stream(durability=...)`，因为 LangGraph 从 runnable config 读这个键，
而且子图会继承它——`stream()` 的参数覆盖不到子图。

### 为什么 `exit` 在这里是安全的

`exit` 会在中途暂停时丢状态，所以必须先排除暂停的可能：

1. **JC 的图从不调用 `interrupt()`。** DeerFlow 的 HITL 审批中间件只在
   `hitl_approval.enabled` 为真时安装，默认 false，JC 的 `config.yaml` 没有这一段。
   实测中间件列表 33 个，没有 Hitl/Approval。
2. **取消也保留状态。** 停按钮会中途丢弃流。实测：正常回合 messages=3；中途丢弃后 messages=4
   （用户消息已落库）；下一回合 messages=6，且能正确回忆前文的暗号。
3. **跨回合记忆正常。** 实测生产环境写入「紫色鲸鱼」，下一轮答出「紫色鲸鱼」。

`tests/test_checkpoint_durability.py` 把这几条钉住：改回 `async` 会失败；有人装上 HITL
中间件也会失败，后者是唯一会让 `exit` 变不安全的变化。

## 代价与边界

- **进程在回合中途崩掉，该回合的模型上下文丢失。** 业务数据（会话、消息、确认）走独立事务，
  不受影响；丢的是 LangGraph 的对话历史，用户重发即可。这是有意的取舍。
- **如果以后数据库搬到同机或内网（<1 ms）**，`async` 也就不再昂贵，但这个设置仍是对的——
  它省掉的是 85 次无用的写入，与链路快慢无关。

## 配套改动

- **观测**：`agentkit.observability` 组件（可复制到其它 agent 服务），暴露
  `llm_call_duration_seconds`、`llm_calls_total`、`llm_tokens_total`、`llm_attempts_per_call`、
  `agent_phase_duration_seconds`、`agent_turns_total`、`method_duration_seconds`、
  `agent_turns_in_flight`，端点 `/metrics`。回合内按 `ttft` / `generate` / `turn` 分段计时，
  这次的结论正是靠它才得到——只看总耗时看不出是数据库。
- **预热**：启动时构建 entry role 的图（`JC_DEERFLOW_PREWARM`，默认开），把冷启动的
  4–8 秒从「部署后第一个用户」挪到启动阶段。
- **前端**：等待提示原先只出现约 0.6 秒。原因是判断条件要求「没有任何活动」，而 harness
  几乎立刻发一个 `skill` 事件。改为判断「还没产出回答文本」，这样 10–16 秒的静默期始终有反馈。

## 教训

1. **版本号相同不等于内容相同。** `build-release.sh --check` 只比版本字符串，把
   `agentkit 0.1.0` 判为最新——而 wheel 里没有新增的 `observability/`。结果是部署时
   `uv sync` 装了旧包、uvicorn 起不来、后端停了。检查应比对内容，不是版本。
2. **跨地域数据库 + 高频写入 = 隐藏的数量级问题。** 单次 500 ms 看起来能忍，乘以 55 就不是。
3. **先量再猜。** 上一轮把「615 次握手」读成「缓存失效」，代价是白查一轮。这次每一步都有
   `rebase` 到真实时间戳的数据支撑，才定位到 checkpointer。
