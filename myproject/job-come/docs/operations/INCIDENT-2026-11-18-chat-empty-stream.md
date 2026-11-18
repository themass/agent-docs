# 事故复盘：chat 空流 P0（2026-11-18，当日关闭）

## 现象

产线对话回合 HTTP 200 但用户得不到回答；日志反复出现
`ValueError: No generations found in stream`（DeerFlow 错误中间件重试 3 次后
落入兜底文案），`jc_llm_call` usage 全 0。

## 根因：同一网关、同一模型上的两把锁（都是流式静默失败）

对 `api.agicto.cn` 实测（2026-11-18）：

1. **temperature 锁**（`b07e91e` 关闭）
   `gpt-6-luna` 只接受 temperature=1。非流式返回 500（可回退）；
   **流式返回 200 + 零 SSE 事件**（静默）。
2. **tools×thinking 互斥锁**（`2dbcb81` 关闭，第一把修复部署后 chat 仍失败才暴露）
   `gpt-6-luna` 上 tools 与活动 reasoning 互斥；非流式 500 明说
   "Function tools with reasoning_effort are not supported"；
   **流式又是 200 + 零事件**。agent 循环每轮带 tools → 每次对话必踩。
   网关不认 `thinking`/`enable_thinking` 体开关，只认顶层
   `reasoning_effort: none`；而 litellm 对无法归类的网关模型会**丢弃顶层
   `reasoning_effort`**，所以修复经 `extra_body` 下发（OpenAI SDK 直接并入 JSON）。

两把锁都是逐模型不是逐网关：glm-5.3-flash / gpt-6-sol / gpt-6-astra /
gpt-6.1-sol / deepseek-v4-pro 均正常。锁表在
`src/jc/llm/transport.py`（`_TEMPERATURE_LOCKED_MODELS`、
`_TOOLS_REQUIRE_REASONING_OFF`），换模型前按注释里的方法重新探测。

## 修复与验证

- 链级判定（litellm 会把调用级参数合并进每个 deployment），只在带 tools 的
  请求上强制 reasoning off；不带 tools 的调用保留配置的 thinking。
- 单测 9 + 12 项（两侧都有）；全量 1140 passed。
- **产线 E2E（部署 bed4d91 后）**：注册新账号 → 图片附件回合 → 流式返回
  「1+1 等于 2。」，历史 1 user + 1 message，无兜底文案。通过。

## 遗留

- 产线回合 usage 行 token 全 0：流上没有 usage 尾块（harness 路径未设
  `stream_options.include_usage`），成本观测在流式路径缺一块，非用户可见故障。
- 验证账号 `usr_pdpsf1t2x0877hsm`、`usr_6clz1dcz2ahpz1xg` 等测试数据待清理。
