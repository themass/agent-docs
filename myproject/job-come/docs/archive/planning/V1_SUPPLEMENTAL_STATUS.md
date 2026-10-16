# V1 补充实现与验收状态

日期：2026-10-14。**本地候选版本可开始测试，不等于生产上线批准；四项工作尚未全部关闭。**

## 1. Agent / MCP / API 公开 JD 读取

已实现：
- `POST /jobs/profiles/{profile_id}/parse-url`：默认静态 GET，显式 `render=true` 使用独立动态浏览器。
- 所有抓取前检查档案权限；静态与浏览器中继共享 DNS 校验、IP 固定、私网阻断、重定向校验、大小与超时限制。
- `jc_job_fetch` 在 handler、FastMCP、OpenAI tool registry 注册；只在 jd-parser / apply-pipeline 的 skill 白名单开放。工具读取不自动解析或保存。
- REST 解析保存来源元数据于 requirements._provenance，无新增数据库 migration；响应及前端展示来源、时间、方式。
- 页面正文视作不可信输入；档案 patch 仍需用户一次性确认，不开放模型自行确认。
- 无登录态、上传、点击、POST、任意调用方法/请求头，不开放通用网络权限。

已验证：URL/DNS/体积/重定向、权限在网络前检查、stdio 与 registry 一致、动态正文/私网请求/POST 三项真实 Chromium 夹具。

**未验证**：真实 DeerFlow → LLM → 工具 → MySQL/Redis/TOS 全链路、真实网站可读性。Playwright 中继与死代理不应当作为生产 OS 沙箱；上线必须另设 worker 隔离、网络 egress 策略及限流/容量门禁。

## 2. 动态浏览器运行验收

- 真实 Chromium 执行动态脚本，验证正文生成、私网动态请求失败关闭、POST 不到达中继。
- 实际 Next production build 前端：勾选动态读取、请求体、岗位匹配、来源显示、错误恢复。
- interviews / bank / applications / campaign / resume-agent / coach-agent 六页实际加载，无 pageerror。
- 结果见 `acceptance-evidence/ui-runtime.json`。API 都是拦截夹具，不是线上数据。
- 入口：本地 frontend 启动后运行 `../../../venv/bin/python scripts/verify_ui.py --base http://127.0.0.1:3107`。

## 3. 文档解析评测（部分完成）

入口：`../../../venv/bin/python scripts/evaluate_documents.py`。

报告：`DOCUMENT_EVALUATION.json`。9 个脱敏输入：5 个不同岗位 TXT、表格 DOCX、双栏 PDF、扫描 PDF、中文 PDF。当前 extractor 与 MarkItDown 0.1.5 各测一次，共 18 条观察。

- 8 个非扫描样本：两者检查字段召回率均 100%（有限 anchor，不是全文/结构准确率）。
- 双栏 PDF：两者都保留 anchor，但阅读顺序不符合原列顺序，不能宣称版面恢复已通过。
- 扫描 PDF：两者 anchor 召回率 0，需要 OCR/vision；未调用生产视觉服务。
- **Docling 已在 `/tmp/jc-docling-eval` 的独立环境安装并启动实测，未修改共享 Python 环境。**

截至 2026-10-14，Docling 本地源码 `/Users/gqli/work/docling` 已通过独立环境实测；使用已缓存的普通文本/布局模型并开启离线模式时，5 个 TXT、表格 DOCX、双栏 PDF、中文 PDF 均完成，非扫描样本 anchor recall 为 100%。扫描 PDF 在未启用 OCR 时可转换但 anchor recall 为 0，这不是 OCR 通过。

评测脚本已支持 `--source`、`--artifacts-path`、`--offline` 和 `--ocr-engine {none,mac,rapidocr}`，并在模型缺失或外部服务错误时立即记录 `blocked_external_model`，不再无条件重试 429。`--artifacts-path` 只接受真正的 Docling 预下载 artifacts 目录；Hugging Face cache 不能冒充该目录。

macOS Vision OCR 当前未能在独立环境启用：`ocrmac`、`Vision` 和 `Quartz` 均不可导入；因此扫描件仍为 blocked，不阻塞 V1 的文本简历闭环。后续若安装原生依赖，只能把结果标记为开发机能力，不代表生产环境跨平台能力。

结论：当前没有证据支持将 Docling 作为所有简历输入的默认替代解析器。V1 继续使用现有解析器处理文本/非扫描输入；Docling 作为复杂版式增强路径，OCR 和跨平台生产化另列发布门禁。

## 4. 导出质量与回归

已修复：
- PDF renderer 失败必须返回 failed，不再以 PDF 状态上传 HTML。
- 指定草稿必须存在且属于当前档案。
- Word 补齐教育、技能、项目及经历地点；中文及双语 HTML/PDF 补齐项目内容。
- PDF 渲染在线程执行，页面外部资源请求全部阻断。
- 上传存储前校验文件格式、全部已知内容字段、PDF 页数 1–6 和文字边界；失败不上传。

样本：三套模板各 PDF/DOCX，共 6 份，检查字段保留率 100%；PDF 为 1 / 1 / 2 页，已查看页面截图，无明显裁切。英文模板兼容中文夹具的测试不代表英文翻译质量验收。

结果：`acceptance-evidence/exports.json`。入口：`../../../venv/bin/python scripts/verify_exports.py`（样本/截图输出 /tmp）。

Word/LibreOffice 已实际渲染：首次渲染发现运行时 Fontconfig 没有系统字体目录，中文显示为方块；已把 DOCX 的东亚字体明确设为 `Heiti SC`，并以包含系统字体目录的 Fontconfig 重渲染，中文、分页、项目/教育/技能内容正常。此为本机 LibreOffice 验收，不代表所有用户机器字体完全一致。

**未完成**：扫描 OCR 与跨平台 Docling/OCR 评测、真实用户长简历视觉矩阵、真实依赖的上线全链路验收。自动文本边界校验不等于所有视觉布局正确。

## 用户现在可以做什么

可以开始本地/测试环境功能验收：上传 → 档案确认 → JD → 匹配 → 简历 → 审稿/导出 → 模拟面试 → 归档 → 题库复练。

正式放行前仍必须关闭：真实 Agent/API/存储依赖联调；Docling/OCR 对比；真实 DOCX 分页；公网域名部署、邮件、监控与回滚。LiveKit、手机端、真实会议监听仍在 V2。
