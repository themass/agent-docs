# T0 实测结果

日期：2026-11-09。脚本在 `spikes/`，可复现。环境：`/tmp/companion-venv`（Python 3.12）。

## T0-1 工厂在无配置文件下构建并流式运行 —— 通过

- 工厂：`create_deerflow_agent(model, tools=[], system_prompt=…, features=RuntimeFeatures(...))`，开关按 P §2.2 设置（sandbox/memory/summarization/subagent/vision/auto_title 关，loop_detection、token_budget 开）。
- 证据：`python spikes/t0_factory_full.py` 输出 `BUILD OK`、`STREAM OK`，假端点收到 1 次请求，系统消息就是我们给的 `你是测试助手。`。
- 负面测试：设置 `DEER_FLOW_CONFIG_PATH=/nonexistent/config.yaml` 同样通过 —— 构建与流式路径不读取配置。
- 注意：`get_app_config` 在代码中仍存在，但调用点在 `summarization_middleware.py`，摘要关闭时不进入。**如果以后打开摘要，需要重新验证。**

## T0-2 mcp 版本 —— 通过（已固定）

- 症状：`mcp==2.3.0` 下 `import deerflow.client` 失败（`McpError` 已改名 `MCPError`）。
- DeerFlow 自己的锁文件（`libs/agentkit/vendor/deer-flow/backend/uv.lock`）锁定：`mcp==1.30.0`、`langchain-mcp-adapters==0.2.2`。
- 结论：固定这两个版本，`deerflow.agents.factory` 与 `deerflow.client` 均可导入。
- 行动：这两个版本必须写进 `pyproject.toml`（T1 处理）。

## T0-3 stream_mode="messages" 的事件形状 —— 已记录

纯文本回合：每个元素是 `(AIMessageChunk, metadata)`，`content` 为增量字符串，`metadata["langgraph_node"] == "model"`。

工具调用回合（`spikes/t0_tool_shape.py`）：

| 事件 | 形状 | 适配器应当 |
|---|---|---|
| 文本增量 | `AIMessageChunk`，`content` 非空，`tool_call_chunks == []` | 发 `message.delta`（经 50ms/64 字符合并） |
| 工具调用开始/参数 | `AIMessageChunk`，`content == ""`，`tool_call_chunks` 非空（先 name+id，再 args 片段） | **不发文本**；这是进入 `phase=tool` 的信号 |
| 空块 | `AIMessageChunk`，`content == ""`，`tool_call_chunks == []` | 忽略 |
| 工具结果 | `ToolMessage`，`name`、`tool_call_id`、`content` | 不对外发送正文；记审计 |
| 第二次模型调用 | 同上，`langgraph_node == "model"` | phase 保持 `tool`：已执行过工具，之后禁止合并（D §6.3） |

适配器规则（写进 T4）：
1. 只把「`content` 非空且无 `tool_call_chunks`」的块当作正文。
2. 首次出现 `tool_call_chunks` 或 `ToolMessage` 时，把回合的 `phase` 置为 `tool`，不可回退。
3. 只实现异步钩子（`abefore_model`、`awrap_model_call`、`awrap_tool_call`）。

## 对设计的影响

- P §2.5 三个待实测项全部关闭。
- D §8.3 的第 1 条（mcp 版本）与第 4 条（冒烟测试）按本结果执行。
- 用 `ask_clarification` 的情况未在本次实测中覆盖（它只是另一个工具，形状相同），由 T4 的单测覆盖。
