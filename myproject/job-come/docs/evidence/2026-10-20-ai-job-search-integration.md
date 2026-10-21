# ai-job-search 方法论集成：实现与验证记录

日期：2026-10-20（Asia/Shanghai）

前置审计：[方法论审计](2026-10-20-ai-job-search-methodology-audit.md)。该审计是实施前快照；以下为用户批准实施后的状态。

## 范围与设计边界

沿用现有 Web → API/MCP → 业务服务 → 存储/渲染链路，不增加 Agent 平台、数据库表、岗位抓取、来源适配或后台任务。不运行付费模型验证，也不修改用户业务数据。

### 1. PDF 文本层质量诊断

- 新增 `pdf_text_quality.py`，由已有 `validate_export()` 调用。
- 内容保留比较使用 NFC、印刷引号/连接符等价和空白归一化，原始档案与产物不变；数字与正负号差异仍受检查。
- 诊断联系方式可提取性、替代字符、私用区字符和非 ASCII 日期连接符。新增警告不阻断导出，日志只包含代码、计数和导出标识，不包含简历正文或联系方式。
- 原有损坏文件、内容缺失和页面边界检查保留。
- 三模板真实 HTML → Chromium PDF → PyMuPDF 提取回归，覆盖中文、联系方式、公司/项目与 bullet 先后顺序。
- 通用阅读顺序仍为 `not_assessed`；样本测试不等于所有简历或所有 ATS 均兼容。不产生 ATS 得分或录用承诺。

### 2. JD 输入诊断

- 新增纯函数 `inspect_jd_text()`，最多扫描 50,000 字符，披露截断；仅返回版本、状态和风险计数。
- 粘贴、现有 URL 读取、MCP 解析共用服务端诊断。静态 URL 读取额外在文本提取前检查原始 HTML；动态浏览仅检查得到的正文，不声称覆盖全部隐藏 DOM/CSS。
- 标记隐藏属性/内联样式、不可见或双向控制字符、有限的中英文指令形态。模型接收明确标记的不可信 JSON 数据；模型返回值不能覆盖服务端诊断。
- 原始输入保留，诊断使用现有 JSON 存储，无迁移。不跟随 JD 内链，不静默删除事实；这是启发式诊断，不是注入攻击防火墙。
- 未新增 JD 风险提示前端 UI。

### 3. 导出与实际投递分离

- HTTP 请求、Web API、MCP handler/server/dispatch、工具描述统一 `create_application=false` 默认值。
- 生成材料/导出不再默认写“已投递”；显式传 true 仍兼容，但语义限定为用户确认已经实际投递。现有历史记录不回写。
- HTTP 参数使用严格布尔值，拒绝将字符串 `"false"` 当成真实意图；MCP dispatch 不再使用 `bool(...)` 强制转换。
- 这不是新增雇主投递能力，也不是服务端可验证用户是否真的提交的凭证。模型仍需遵守用户意图边界。
- 发现旧 MCP interceptor 查询尚未生成的“最新草稿”，并把模型 review 与投递记录绑定，违背现有 review 非阻断契约。移除该过期阻断；保留工厂入口兼容已部署配置。归属校验、产物完整性和持久化仍由业务服务负责，未绕过这些检查。

### 4. 现有 Skill 方法论增强

- Apply-pipeline：提议、确认保存、读回、导出、实际提交分别判定成功；失败停止，不盲目重试或提前宣称完成。
- Coach：用户提供的新事实走既有正式写入流程，不只留在聊天中。
- Writer：JD 要求映射到候选人证据，优先相关性与独特贡献，不编造关键词或为页数静默丢弃亮点。
- Reviewer：独立、只读、字段级证据；分开评估事实、匹配度和最终文件质量。
- 沿用既有提示词组合，不增设多 Agent 调度或重复上下文。

## 复用与授权

复核上游 revision：`64a6c90ec32438742ca62f8f30f55afea4435172`。借鉴方法论而非搬入上游脚本、权限、来源适配和本地文件归档。归属记录见根目录 `THIRD_PARTY_NOTICES.md`，MIT 原文见 `docs/third-party/ai-job-search.LICENSE`。

## 验证结果

- 完整后端：**1031 passed, 6 skipped, 10 warnings**，36.09 秒。
- 新增 PDF 专项：**8 passed**，包含三个真实模板渲染；已包含在上述最终全量结果中，不重复累加。
- 前端 Node 测试：**51 passed, 0 failed**，包含默认不登记投递/显式登记的 API 测试。
- 前端 TypeScript：`tsc --noEmit` 通过。
- 新模块及直接相关小文件 Ruff 检查通过；`git diff --check` 通过。
- 测试使用 mock/测试数据库及本地渲染，不调用真实付费模型、不操作用户业务库。跳过项不算通过。
- 警告包含 PyMuPDF 弃用提醒、测试 fixture 的 SQLAlchemy/Pydantic/Pillow 提醒及 LiteLLM 日志协程提醒；未宣称已消除这些独立问题。

最终全量命令（项目根）：

```sh
LANGFUSE_TRACING_ENABLED=false OTEL_SDK_DISABLED=true ../../../venv/bin/python -m pytest backend/server/tests -q --tb=short
```

本机输出：`/private/tmp/jc-ai-job-search-regression-complete.txt`；前端输出：`/private/tmp/jc-ai-job-search-web-tests.txt`。

## 部署与未验收边界

- 本轮安装共享开发虚拟环境的 Playwright 及 Chromium，完成真实 PDF 验证；生产环境仍需使用现有部署路径安装匹配的浏览器运行时，不能依赖本机缓存。
- 无新数据库迁移，本轮不需要用户执行建表脚本。
- 未重启当前服务，未部署线上，未做登录用户在真实运行服务上的全链路验收，也未调用雇主 ATS 系统。
- 未新增 PDF 诊断后台 UI；当前为内部质量结果与日志信号。
- 未在本轮修复/验收历史所有上传、Agent 修改、头像、预览和超时问题。完整单元/集成回归不等于真实供应商响应与线上体验均已验收。
