# TECH-LLM：模型路由、文档解析与可观测性

- **状态**：V1 实现与发布检查依据
- **最后更新**：2026-10-15

## 1. LLM 路由

- 路由配置：`backend/agent/llm/routing.yaml`；模板：`routing.example.yaml`。
- 服务端通过 `backend/server/src/jc/llm/` 调用模型，业务代码不得散落直连供应商 HTTP 请求。
- **凭证分层**：`routing.yaml` 只写模型 slug 与 **provider 名**；`providers.*` 把每个 profile 映射到 `.env` 里的 `api_base_env` / `api_key_env` 变量名（密钥不进 Git）。同一 scenario 内可按条目指定不同 `provider`，或内联 `api_base_env` / `api_key_env`。
- 逻辑开关：`JC_LLM_ENABLED`、`JC_LLM_ROUTING_PATH`。默认文本网关 `JC_LLM_API_*`，视觉 `JC_LLM_VISION_*`；多供应商时在 `.env` 增加如 `JC_LLM_ANTHROPIC_API_BASE` 并在 `providers` 注册。`OPENAI_*` 保留给本地 LiteLLM 代理栈。
- 逻辑模型名：`jc-fast`、`jc-vision` 等；真实 slug 在 `routing.yaml`。
- `JC_LLM_ENABLED=true` 才执行真实解析/优化；无有效模型配置时应明确失败或降级，不得伪造成功结果。
- LiteLLM 使用本地 model cost map（`LITELLM_LOCAL_MODEL_COST_MAP=true`），启动时不应为了加载成本表访问通用互联网。

## 2. 文档解析流水线

```text
上传文件（PDF / DOCX / TXT / 图片；旧版 .doc 提示转 docx）
  → MIME/大小/权限校验
  → 多路由并行尝试（见下表），取质量分最高结果
  → LLM 结构化为档案草稿
  → 用户核对与确认
```

| 格式 | Route A（确定性） | Route B（本地增强） | 视觉路由 |
|------|-------------------|------------------|----------|
| **PDF** | PyMuPDF 文字层 → `ingest_fast` | Route A 无有效草稿时，MarkItDown bytes stream → `ingest_fast` | 前 5 页渲染 PNG → `vision` |
| **DOCX** | `word/document.xml` → `ingest_fast` | 质量不足或结构化失败时，MarkItDown bytes stream → `ingest_fast` | `word/media/*` 内嵌图 → `vision` |
| **TXT** | 全文 → `ingest_fast` | — | — |
| **图片** | — | — | 整文件 → `vision` |
| **.doc** | 不支持 | — | 返回友好提示，请另存为 docx |

- Route B 是服务端受控依赖 `markitdown==0.1.5`：仅接收本次上传的内存 bytes、禁用插件、不提供 URL 或任意服务器路径；输入不超过 10 MB，转换在工作线程执行并有 12 秒超时，输出最多保留 50,000 字符；它不是 Agent/MCP 工具，不扩大浏览器、网络或文件系统权限。
- 同一文件可**同时**走文本与视觉（例如 PDF 既有可复制文字又有扫描页；Word 正文 + 内嵌证件照），由 `payload_quality_score` 选最优草稿，失败路由只记日志。
- 文档解析输出是**草稿**，不是用户已确认事实。
- **可复制的 PDF 文字层**走 `ingest_fast`；**扫描页 / 图片 / 内嵌图**走 `vision`（如 `qwen-vl-ocr`），与文本链分离。
- JSON 任务把空响应、非 JSON、无 choices/message 和 schema 不匹配视为可控的 endpoint 失败；同一 scenario 会继续尝试下一个模型。日志只保留错误类别、文件名、路由与响应元信息，不能记录简历正文、密钥或模型响应全文。
- 文档解析评测应使用固定样本、可比较指标和错误样例；机器结果写入 `docs/evidence/document-evaluation.json`，不替代发布结论。

## 3. 简历生成与导出质量

1. 从已确认档案生成优化稿；
2. 用 reviewer prompt 做事实、结构、语言与岗位针对性检查；
3. 保留 `elevation_map`，使用户能看见表达上的变化；
4. 生成 HTML、PDF、DOCX；
5. 对中英文、分页、字体、链接和下载链做实际检查。

浏览器不可用、生成失败、TOS 上传失败必须以可见错误结束；不得把缺失导出物当作成功。

## 4. 可观测性

- Langfuse 是可选的 LLM trace 后端。配置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST` 后开启 `LANGFUSE_TRACING=true`。
- Trace 应关联请求、用户匿名标识/会话、模型、skill/tool、耗时、token、错误与取消；不要记录明文密码、密钥或不必要的完整敏感档案。
- 生产发布必须有 API 错误日志、Agent/工具调用审计、依赖健康检查和告警策略。详细操作见 [`../operations/OPS-DEVELOPMENT.md`](../operations/OPS-DEVELOPMENT.md)。
