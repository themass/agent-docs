# 上传解析再次超时：证据、修复和验收边界

## 已确认的故障（本地 api.log，2026-10-19）

- 23:48:17 原生 PDF 文字提取成功：route=text，reason=readable_text_layer，text_chars=1686；本地阶段约 2 秒。
- 23:49:33 结构化失败，三次模型请求均为 timeout value=25；pipeline elapsed_ms=77397。
- 23:50:22—23:51:39 又一次相同的文本路线请求重现该问题。
- 未进入 OCR。因此继续优化 OCR 或建议用户换文字版文件不针对这次失败。
- routing.yaml 的 ingest_fast 三个模型均为 gateway provider，配置 timeout_sec=120；ProfileStructurer 的调用级 timeout_seconds=25 覆盖了配置。原实现是非流式，必须等完整 JSON 才能返回。
- 日志只能证明整包请求在 25 秒窗口内未完成，不能区分网关没有响应、模型生成过慢，或不支持相关调用参数；未证明 thinking 是否是原因。

## 修复

1. 新增 llm/buffered_stream.py，ProfileStructurer 选择内部流式接收、外部完整结果的调用模式。不是把未完成 JSON 发给业务层，更不是把失败转成 mock 成功。
2. 文本模型保留 25 秒连接/读空闲上限；生成持续有数据时可以超过 25 秒，但仍受原 pipeline 的 120 秒总预算约束。vision 仍为原非流式请求，不宣称本次修复已覆盖其生成时限。
3. 按现有 transport 的配置模型依次尝试，每个别名最多一次。禁止 SDK 的嵌套 fallback（含 midstream fallback）；消费失败、截断、JSON/schema/非空校验失败才能切换。总截止/取消不启动下一模型。
4. 必须正常结束并带 stop 终止原因才接受结果；空档案、被 length 截断的结果不能保存。退出时关闭流；一次逻辑调用仍写一条审计记录，保存失败尝试与完整成功结果。
5. 新增 start / first_chunk / validated / failed 耗时日志，不打印简历正文。超时保留为 llm_timeout 类别，用户提示不再错误归因到文件格式。
6. 首次解析失败且无档案事实时，页面只显示失败恢复入口，禁用核对/优化/导出和确认动作；后端同样禁止确认空档案或进行中解析。替换失败但已有真实档案时，保留原内容和查看/编辑能力。

## 已执行验证（无真实模型或业务数据库调用）

- 解析/传输定向后端测试：76 passed（5 个 PyMuPDF 旧接口警告）。
- 全部前端 .test.cjs：41 passed。
- 前端 tsc --noEmit --incremental false：通过。
- 本次涉及的 Python 文件 Ruff 与 git diff --check：通过。
- 覆盖活跃流生成超过 idle 上限、停滞流故障切换、全部端点超时审计、部分 JSON 丢弃、错误 JSON 后切换、异常 finish_reason、总截止取消和关闭流，以及上传失败/原档案保留/空档案确认保护。

## 未通过的扩展回归，不隐瞒

额外运行已有的 LLM router/transport/stream/audit 测试时，以下四项失败；排除新增 buffered_stream 测试、不进入新流式分支的组合运行仍重现 4 failed / 35 passed：

- test_validator_failure_is_recorded_as_a_content_failure
- test_total_failure_is_recorded_before_the_error_propagates
- test_a_long_chain_reaches_every_endpoint_even_past_the_second_hop
- test_a_broken_audit_log_does_not_break_the_users_request

单独运行 test_llm_call_log.py 为 28 passed / 1 failed，剩下的长链用例断言最后端点必须重复调用两次，但当前执行仅一次。组合用例还出现 LiteLLM 异步日志 worker 协程未等待警告。不能把整个 LLM 审计回归宣称为全绿；本次没有放宽这些用例的断言来掩盖结果。

## 尚未验收

未请求付费网关、未重新解析用户原文件，因此不能声称生产模型服务已恢复或承诺解析秒数。真实文件后续若仍失败，新日志需要区分 first_chunk 是否出现、哪个模型在哪个阶段退出。未增加表、无需数据库迁移；未重启或杀死用户本地服务。
