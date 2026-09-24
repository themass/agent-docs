# JobCome 下一步工作计划

> 更新：2026-09-06 · 投递物三轨（中文 / 英文 / 双语对照）；产品 UI 仍为中文

## 本轮已完成

| 项 | 交付 |
|----|------|
| Token 分桶 | SSE `context_usage` 按真实 `prompt_tokens` 切分；overhead 短轮次按比例缩放 |
| summarization | `window × 0.16`（200K → 32K）；可用 `JOB_COME_SUMMARIZATION_TRIGGER_TOKENS` 覆盖 |
| 演示账号 | 登录页开发态「填入演示账号」；`python scripts/seed_demo.py` |
| 中英双轨 | `zh-one-page` / `en-two-page` / `zh-en-bilingual`；中文 UI 三轨切换 |
| 回归样本 | 3 简历 + 6 JD 落盘；`./scripts/regression_smoke.sh` |
| Steer cancel | cancel 时补 `[cancelled]` tool_result；E2E 断言无半拉 tool |
| Reviewer issues | ExportPanel 列出 severity / field / message |
| 切档案重置会话 | 切换 profile 中止当前流，不自动恢复上一份档案的 thread |

## 验收

```bash
cd job-come
python -m pytest tests/test_context_usage.py tests/test_resume_locale.py tests/test_steer_cancel.py tests/test_agent_stream_persistence.py tests/test_export_pdf.py tests/test_resume_draft_builder.py -q
python scripts/seed_demo.py
./scripts/dev.sh
# 另开终端
./scripts/regression_smoke.sh
# Agent 多轮 + cancel
export JOB_COME_E2E_EMAIL=demo@jobcome.local JOB_COME_E2E_PASSWORD='Demo1234!'
./scripts/agent_e2e.sh
```

## 简历语言轨（已实施）

产品 UI 始终中文。投递物三选一：

- `zh-CN` → `zh-one-page`（中文一页）
- `en-US` → `en-two-page`（英文最多两页）
- `zh-en` → `zh-en-bilingual`（同一文件：中文全文 + 分页 + 英文全文）

上传后后台 `prepare_tracks`；核对页只改原文事实；译文走 `payload.i18n`。详见 [中英简历方案.md](中英简历方案.md)。

## 下一批（开源借鉴落地）

过滤器先于 Scout。分期见 [开源借鉴落地计划.md](开源借鉴落地计划.md)：W1 URL 抓 JD + 匹配报告 + **始终可拔高** → W2 投递状态机 → W3 Cover 起草 → W4 出处与绑稿 → W5 解析进出口 → W6+ 只读发现。匹配分不阻断优化/导出。

## P2 backlog

- assistant-ui 第二套 UI 或删除
- RunManager 级 cancel
- pdf-inspector / Docling
- Playwright 导出 E2E
