# ai-job-search 对舟卡 Agent / Skill / 导出流程的方法论审计

- 日期：2026-10-20
- 范围：仅研究 `MadsLorentzen/ai-job-search` 的 Agent、Skills、PDF/ATS 校验与申请工作流；不开发职位抓取、岗位来源 Adapter 或岗位推荐数据管道。
- 上游审计版本：本地只读浅克隆的 `master` HEAD（审计时）；项目许可证为 MIT，复用代码仍需保留版权与许可证声明，并逐文件核对依赖许可。
- 本轮性质：审计和改进建议，不修改生产行为、不新增迁移、不改变用户流程。

## 结论摘要

舟卡并不缺少 Agent 分工、Skill 边界、简历事实规则、用户确认、PDF 产物验证等基础机制。JC 已有较强的分层和业务约束，不能把上游项目更长的 prompt 或更多 Agent 数量误当成更成熟。

上游最值得借鉴的不是整套本地 Claude Code 工作流，而是以下三类可迁移方法：

1. 对编译后的最终 PDF 进行独立机器可读性验证，并用真实 fixture 锁定曾发生的提取问题。
2. 将职位正文等外部内容视为不可信数据；除 prompt 规则外，用确定性检查标出隐藏文本、不可见字符和指令形态内容，并通过测试确保所有相关入口都经过检查。
3. 用只读、无写权限的 Reviewer 与 Drafter 分离；Reviewer 输出定位到字段的意见，最终修改、写入仍由受控业务流程完成。

## 已核对的上游实现

审计范围包括：

- `.claude/commands/apply.md`：分阶段 apply 编排，含岗位评估、CV/求职信草拟、独立 Reviewer、编译与检查、最终核对。
- `.claude/agents/application-reviewer.md`：Reviewer 没有 Edit/Write 工具，建议以 `old_string/new_string` 返回；要求所有建议可由候选人档案证据支持；明确职位正文是非可信输入。
- `.claude/agents/posting-scorer.md`：职位批量评分时要求先跑 integrity gate，并按状态返回 scored/expired/unreachable。
- `.claude/commands/outcome.md`、`interview.md`：申请结果、阶段化面试准备、从用户确认的事实补充档案。
- `tools/verify_pdf.py` 与 `tests/test_verify_pdf.py`：提取真实 PDF 文本层，优先 pypdf、回退 Poppler；支持规范化文本匹配、页数和日期字符检查，并以多类回归 fixture 验证。
- `tools/posting_guard.py`、`tools/security_guards.py` 与相应测试：外部岗位正文完整性扫描及入口接线测试；项目明确说明它是确定性提示门，不是安全 oracle。

## 舟卡现状对照

### A. 已有，不应重复造

- **Skill 与工具权限边界**：`backend/server/src/jc/agent/roles.py` 维护 `SKILL_SCOPE`；简历教练、写手、Reviewer、JD Parser、apply-pipeline 的能力范围分开。
- **事实来源与不可信输入原则**：多个 prompt/Skill 明确 profile、JD、附件、回答均为数据而非指令；简历写作约束也要求事实必须有来源。
- **独立简历 Reviewer**：`backend/agent/skills/public/resume-reviewer/SKILL.md` 与导出拦截器构成现有 review 路径；已有按字段定位 issue 的结构。
- **PDF/导出基础质检**：`backend/server/src/jc/services/export_quality.py` 校验 PDF 签名、页数范围、文字边界和档案文本保留；现有 `test_export_quality.py` 覆盖多模板导出、缺失内容和错误 PDF。
- **应用流程与面试准备**：`backend/server/src/jc/services/apply_pipeline_service.py`、`application_service.py` 已承担评估、生成草稿、导出、申请记录与面试上下文。上游文件型 archive/本地 tracker 不适合再并行引入。

### B. 需要明确审计的可能缺口

1. **ATS 文本层的细项覆盖**：JC 已抽取 PDF 文本并检查档案预期内容是否保留，但需用实际导出 fixture 逐项验证：联系方式可提取、阅读顺序可接受、CJK/特殊字体无乱码、日期与项目标题在抽取结果中完整。未逐项证实前不能宣称缺失，也不能宣称已覆盖。
2. **外部 JD 的确定性 integrity gate**：JC 已有不可信数据 prompt 规则、公共 URL 安全读取限制和网络请求安全测试；但目前检索到的测试主要验证 URL/HTTP 行为，并未证明有类似 posting_guard 的正文层隐藏内容/不可见字符/指令形态扫描以及所有入口的接线测试。可考虑加一个只做标记、不改写 JD 的结构化诊断器。
3. **Apply 状态语义需核实**：`ApplyPipelineService.run()` 在成功导出且 `create_application=True` 时调用 `mark_applied()`；`ApplyPipelineRequest.create_application` 默认值为 true，Web API 也显式提交 true。生成并导出材料并不必然等于用户已经向雇主提交申请。需要检查 UI 的按钮语义、接口调用时机和用户预期，再决定是否拆分“材料已准备/待提交”与“用户已投递”。本审计不擅自更改该状态语义。
4. **真实最终产物与确认版本的关联**：现有 export quality 能验证内容保留，但应补测试确保被导出的 draft_id/版本就是用户确认的版本，并且状态只在数据库写入、读回和导出校验成功后被标记完成。

## 建议迁移的方法

### P0：导出验证差距矩阵（不改变用户体验）

对现有 `validate_export()` 使用舟卡三个模板与中英文 fixture，保存/断言提取文本。记录以下检查结果：

- 关键联系方式是否可提取；
- 文本提取是否包含乱码/替代字符；
- 日期、职位、公司和 bullet 是否在抽取层完整；
- 多栏/区块的阅读顺序是否会造成语义错位；
- PDF 页面数和几何边界仍由现有规则负责。

ATS 关键词覆盖只能做“提示”，不得作为事实生成依据或声称保证通过招聘系统。初始新增规则建议仅返回诊断 warning，不阻断导出；只有真实 fixture 证明确定性且低误报后才讨论阻断级别。

### P1：JD integrity gate（只标记，不抓取）

若后续实施，应在既有 JD URL/粘贴正文进入解析和 Agent 之前统一运行，返回有限结构化信号（例如隐藏文本、不可见字符、疑似指令行、可疑隐藏 URL 计数）。保留原始正文用于追溯，模型分析基于明确标记后的安全输入；不执行内容中的指令，不因扫描结果静默删除候选人/职位事实。添加入口接线测试，证明 URL 与粘贴入口不会绕过。

此工作与岗位抓取/Adapter 无关，不增加外部来源，也不自动跟随 JD 内链。

### P2：流程语义和状态审计

将“评估、草稿、review、用户确认、导出、用户实际提交、申请结果”分别定义为可观察状态；尤其验证“导出成功”不被误当作“实际已投递”。任何状态迁移需要对照前端文案和 API 调用做兼容方案，不能只改枚举。

### P3：Skill/Agent 迁移原则

- 采纳上游 Reviewer 的只读能力原则；禁止 Reviewer 自己写库/改档案。
- 每个 Agent 只接收完成当前阶段所需的档案/JD/草稿，不重复传整套无关上下文。
- Reviewer 产出字段级问题和证据引用；业务服务而非模型判定是否阻断。
- 用户确认的新事实必须进入档案的正式确认/持久化流程，不能只留在对话或临时草稿。
- Apply-pipeline Skill 写明每阶段的工具、成功条件、失败条件和禁止的副作用；工具返回成功不等于后续保存/导出已成功。

这些原则与 JC 当前方向基本一致，重点是补齐可测试契约，而不是复制英文 prompt 文本或增加 Agent 数量。

## 明确不在本阶段做

- 不开发职位抓取、来源 Adapter、职位聚合数据库或推荐任务。
- 不搬入上游本地文件 archive、Claude Code 命令/设置或特定丹麦招聘入口。
- 不改简历模板、PDF 引擎、现有用户流程或申请状态。
- 不把 ATS 关键词覆盖包装成通过率/录用承诺。
- 不把上游项目的经验性规则当成已被舟卡数据验证的行业结论。

## 下一步执行顺序

1. 先运行/扩展现有导出测试 fixture，完成 ATS 文本层覆盖矩阵；只补上已经证实缺失且低误报的校验。
2. 单独增加 JD 正文 integrity gate 的纯函数测试和入口接线测试，先输出诊断而非拦截。
3. 用 UI/API 测试追踪 `create_application` 语义；单独提出向后兼容的状态方案，不在本次静默改变行为。
4. 完成后跑相关后端测试与前端 apply/export 测试，并在证据记录中列出通过项、未覆盖项和误报风险。

## 本地验证记录

运行命令：`../../../venv/bin/pytest backend/server/tests/test_export_quality.py backend/server/tests/test_export_html.py backend/server/tests/test_export_pdf.py`（从 `myproject/job-come` 执行）。结果：23 passed、4 failed。4 个失败都因当前 Python 环境缺少 Playwright（`ModuleNotFoundError: No module named 'playwright'`），集中在真实 HTML→PDF 渲染的模板/导出测试；HTML 质检和基于 PyMuPDF 直接构造 PDF 的内容检查通过。该失败说明本轮环境无法完成真实最终产物的端到端验证，不能据此判断 PDF 检查逻辑有回归或通过。


## 用户批准后的实施进展（2026-10-20）

以上保留为实施前审计快照。后续已完成 PDF 文本层诊断、JD 风险标记、默认不登记实际投递与 Skill 方法论增强，真实 PDF 渲染依赖已补齐；最终全量后端 1031 passed、6 skipped，前端 51 passed。具体行为变更、授权和未验收边界见 [实施记录](2026-10-20-ai-job-search-integration.md)，不能再用上面的缺 Playwright 结果代表当前状态。
