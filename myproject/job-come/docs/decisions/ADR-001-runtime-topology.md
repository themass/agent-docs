# ADR-001：使用同域 Web + API，并将 DeerFlow 嵌入 API 进程

- **状态**：Accepted
- **日期**：2026-10-15

## Context

JC 是 Web 产品，需要让前端、登录 cookie、API、Agent 会话和数据访问形成稳定的上线闭环。V1 团队与部署复杂度有限，不适合先拆出独立 Agent 网关和跨域前端接口。

## Decision

- Next.js Web 位于 `frontend/web/`；FastAPI 位于 `backend/server/`。
- Nginx 在 `http://jc.sspacee.com` 提供同域入口：`/` 转发 Web，`/api/v1/*` 转发 API。
- DeerFlow Agent 作为 FastAPI 服务内的受控运行时，而非单独公网进程。

## Consequences

- 浏览器使用相对 `/api/v1`，减少 CORS 和 cookie 域问题。
- API 与 Agent 可共享认证、业务服务、审计与权限边界。
- Agent 进程级状态、并发隔离和恢复必须持续监控；达到瓶颈时再评估独立运行时。

## Alternatives considered

- **独立 Agent 服务**：隔离更强，但需新增会话鉴权、事件协议、部署和观测链路；V1 成本过高。
- **前端直连模型/Agent**：无法可靠保护密钥、档案归属与工具权限，拒绝。
