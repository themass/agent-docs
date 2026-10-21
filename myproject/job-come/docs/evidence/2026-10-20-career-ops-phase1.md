# career-ops 方法论集成：第一批实现与验收

日期：2026-10-20，Asia/Shanghai。

## 用户批准的分期与本轮范围

本轮实施第一批：任务上下文、用户纠正约束、岗位要求证据映射。
第二批的故事库、面试准备/复盘闭环、求职信和邮件草稿未在本轮实施。
不做岗位抓取、来源适配、自动投递、邮件发送或第三方 memory 集成。

## 代码落点

- `domain/profile_context.py`：纯函数档案索引、字段/列表/长字符串分页、完整性披露，写手/匹配事实投影。
- `agent/resume_task.py`、`standing_instructions.py`、`services/agent_service.py`：每轮小型实时索引、版本与长度日志；方法论留在 system 层。
- `mcp/handlers.py`、`server.py`、`agent/tool_catalog.py`：默认索引，按需读取，仍先检查归属。
- `schemas/profile_payload.py`、`services/profile_patch_ops.py`：带稳定实体范围的否认表述；复用原确认卡、CAS、数据库 JSON 和历史版本。
- `domain/claim_constraints.py`、`services/resume_service.py`：生产质检检测指定范围的表述复现，不依赖模型二次判定；保持现有非阻断契约。
- `domain/fit_evidence.py`、`schemas/job.py`、`services/fit_score_service.py`：逐要求引用校验，禁止拿被否认材料当正向依据，替代原 JSON 字符串硬截断。
- `services/job_service.py`、MCP handler：同结构落入已有 fit_report JSON，携带评估时档案版本。
- `frontend/web/components/job/RequirementEvidenceList.tsx`：沿用已有样式 token，默认折叠，显示来源原文、未知与待补问题；实际引用只按评估版本核对。
- 现有 writer/reviewer/mock Skill references 增加约束规则，不增加平行 Agent。

## 验收重点

- 大档案连续两次生产 AgentService 调用均不注入全量经历，版本随消息绑定；不只测试独立 helper。
- 字段不截断；超长字符串显式分块后可逐字重组，列表和嵌套 highlights 均可分页；越权读取继续拒绝。
- 用户纠正先生成真实 pending 确认，再确认写入、提交并重新查询；使用共享数据库而非进程/本地记忆。
- 范围绑定 ID，不随列表排序漂移，不污染另一段经历；可删除；生产 review 合并能标记模型漏过的同文复现。
- 假路径、假引用、被否认旧材料均不能成为 verified 引用；缺证据不标成无能力；额外编造的岗位要求不进入报告。
- HTTP 业务入口和 MCP 入口分别测试，写入结果通过 Web JobResponse 读回一致。
- 前端 React 实际渲染测试：旧报告不凭空显示行、默认折叠、未知文案、版本标识、HTML 转义。

## 重要边界

1. 字符预算不是模型 tokenizer 的精确 token 预算；没有对历史 checkpoint 进行破坏性清理。旧会话仍可能携带早期大上下文。
2. 主简历生成与岗位匹配仍需其业务所需的完整事实，只移除非证据/重复渲染数据；不为省 token 隐藏经历。
3. 确定性纠正检测只匹配归一化同文；不保证覆盖语义改写或跨语言翻译。实体级规则需要输出保留源 ID，不能把未知归属扩大到全局。
4. 引用校验只证明路径与源文存在，语义相关性和重要性仍是模型建议，不声称匹配分已获真实招聘结果校准。
5. 无新表、无迁移、无付费模型调用、无业务库修改。未重启/部署实际服务，未进行登录浏览器真机验收或真实供应商端到端验证。
6. 使用 frontend-ui-engineering 的组件/可访问性原则，复用现有设计 token；未使用 OpenDesign 生成设计稿。

## 复用授权

借鉴上游 Skill 的按模式加载、用户否认表述约束及岗位逐要求解释方法，按 JC 架构独立实现。
没有复制上游 CLI、文件主存储、扫描程序或品牌。来源和 MIT 许可见根目录 THIRD_PARTY_NOTICES.md 及 docs/third-party/career-ops.LICENSE。

## 最终回归结果

在项目根目录执行后端全量回归：

```sh
LANGFUSE_TRACING_ENABLED=false OTEL_SDK_DISABLED=true ../../../venv/bin/python -m pytest backend/server/tests -q --tb=short
```

结果：**1069 passed, 6 skipped, 10 warnings，37.74 秒**。完整输出保存在本次开发机 `/private/tmp/jc-career-complete.txt`，临时测试输出不是业务存储。警告涉及已有 PyMuPDF、SQLAlchemy 测试夹具、LiteLLM、Pillow 和 Pydantic，不代表这些既有警告已修复。

在 `frontend/web` 执行：

```sh
node --test tests/*.test.cjs
./node_modules/.bin/tsc --noEmit
```

结果：**54 passed, 0 failed**；TypeScript 检查退出成功。输出分别保存在本次开发机 `/private/tmp/jc-career-web.txt` 和 `/private/tmp/jc-career-types.txt`。

新增模块、核心变更与新增测试的定向 Ruff 检查通过；`git diff --check` 通过。未对已有脏文件做全局格式化。上述验证不包含付费供应商调用、生产业务数据库写入、登录态浏览器验收或服务部署；不能据此声称真实模型全链路已经验收完成。
