# TECH-API：HTTP、认证与接口契约

- **状态**：V1 已实现接口的开发约定
- **最后更新**：2026-10-16
- **权威来源**：FastAPI OpenAPI：本地 `/docs`（仅当 `JC_DOCS_ENABLED=true`）及 `backend/server/src/jc/api/` 的 Pydantic schema。

## 1. 对外边界

- API 根路径固定为 `/api/v1`；浏览器通过同域相对路径访问。
- 生产流量由 Nginx 把 `/api/v1/*` 转发到 FastAPI，前端不得内嵌服务端 host 或端口。
- OpenAPI 描述与 Pydantic 请求/响应模型是字段级接口契约；本文件不复制每个 schema，避免第二份过期 API 文档。

## 2. 资源分组

| 路由前缀 | 责任 |
|---|---|
| `/auth` | 注册、登录、登出、账户设置、双路径邮箱验证、密码找回与会话上下文 |
| `/profiles`、`/resumes` | 简历上传、档案草稿/确认、证据补全、优化、导出前质检、导出（`pdf` / `docx` / `html`，三者内容一致） |
| `/jobs` | JD 粘贴/受限读取、解析、匹配与申请准备流程 |
| `/coach` | 模拟面试、题库、回答、真实面试归档 |
| `/agent` | Agent session、SSE 消息流、取消与历史消息 |
| `/campaign`、`/notifications` | 机会准备节奏、站内通知 |
| `/admin` | 受限运维/审计能力，必须额外鉴权 |

## 3. 接口规则

1. **身份与资源归属**：每个需登录的接口先解析 session，再检查 profile、job、session、export 等资源归属；不得仅相信客户端传入的 ID。
2. **版本与演进**：新增字段使用可选/可兼容的方式；破坏性变化通过 `/api/v2` 或明确迁移计划处理。
3. **输入验证**：在路由/Pydantic 边界完成格式、枚举、大小和权限校验；服务层接收已校验数据。
4. **错误格式**：沿用 FastAPI/Pydantic 的结构化错误，业务错误应有稳定的 HTTP 状态与可显示信息，不泄露堆栈、密钥或内部对象 key。
5. **状态变更**：确认档案、保存回答、创建导出等写操作必须可追踪；对可能被客户端重试的高价值写操作评估幂等性。
6. **流式响应**：Agent SSE 事件需有稳定事件类型和终止事件；取消、失败和工具调用必须可被客户端区分。

## 4. 账户与邮箱验证契约

- `GET /auth/account`、`PATCH /auth/account`：只允许已登录用户读取或更新自己的显示名称、界面语言和默认表达力度；V1 不支持直接修改邮箱。
- 注册和 `POST /auth/resend-verification` 会发送同一封验证邮件，邮件内同时包含一次性验证链接和 4 位数字验证码。
- `POST /auth/verify-email` 接收链接 token；`POST /auth/verify-email-code` 只允许已登录用户提交自己的 4 位验证码。
- 每次重发都会使旧链接和旧验证码失效；验证码采用 TTL、哈希存储和最多 5 次失败尝试限制。验证成功后两种凭据均失效。

## 5. 高风险接口附加约束

- 档案事实变更只能由用户确认提交；模型产生的是建议或待确认 patch。
- `GET /profiles/{id}/evidence-gaps` 与 `POST /profiles/{id}/evidence-answers` 是**用户补充事实**的通道，
  不是模型写入通道：前者为确定性扫描（无模型调用），后者只向 `payload.evidence_answers` **追加**用户亲笔内容
  并递增 `version`，不修改任何既有要点。方法论与信任等级见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 9 节。
- `GET /profiles/{id}/writing-options` 与 `PUT /profiles/{id}/writing-options` 读写目标岗位族与包装角度
  （最多 2 个）。这两项是**纯呈现偏好**而非事实，因此允许直接写入 `payload.preferences`，
  无需走档案确认流程；未知 id 忽略而不报错，空值表示恢复岗位族推荐。角度**不放宽**审稿门禁——
  例如 `ownership` 角度下把源文 `参与` 写成 `主导` 仍然阻断。方法论见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 11 节。
- `GET /profiles/{id}/export/review` 的 `diagnostics` 字段为确定性体检结果（篇幅、要点长度、岗位用词覆盖），
  **一律为建议**，不参与 `can_export` 判定；只有 reviewer 的 `error` 级问题阻断导出。
- 优化预览与导出前质检均返回 `coverage`（源档案要点是否仍在生成稿中）。**覆盖度一律为建议，
  不参与 `can_export` 判定**：合并重复要点有时是正确的编辑决定。判定标准与阈值依据见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 12 节。
- `GET /profiles/{id}/export/review` 的 `issues` 里，`code` 以 `invariant_` 开头的条目来自**确定性**
  不变量审计（`writing_invariants`），不是审稿模型的判断：它只断言「这个数字 / 这个主导动词在档案
  任何位置都找不到依据」。这类条目**一律 `severity: warning`**，不参与 `can_export`——
  合并要点会打断归因，确定性阻断会在正确写作时误伤，把用户锁在自己的文档外面。
  审稿已就同一 `field` 报过的问题会被去重。判定类型与豁免见
  [`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 14 节。
- `jc_job_fetch` 的 HTTP 读取属于受限服务端能力，详细网络边界见 [`TECH-AGENT.md`](TECH-AGENT.md)。
- 上传、导出、下载均需校验用户归属；对象存储 key 不构成授权凭据。

## 6. 变更流程

修改 API 前后必须同时检查：路由、Pydantic schema、前端 API client、鉴权/归属测试、OpenAPI 变化和 [`../operations/QA-TESTING.md`](../operations/QA-TESTING.md) 的回归范围。
