# 预览复用与取消清理回归

日期：2026-10-19，Asia/Shanghai。

## 证据与边界

- 已读取 `.data/logs/dev/api.log`：20:07:40 存在用户报告的 close / invalidate `IllegalStateChangeError`。紧邻 writing-options 的 HTTP 行不能证明异常属于该接口；旧日志没有足够关联字段，不能据此确定某次预览提速的唯一原因。
- 本次复现：已取消的 AnyIO scope 会再次中断 producer 的异步退出，依赖清理可能先关闭其 DB session。另复现 ASGI 2.4 发送失败时 response 未及时关闭悬停在 yield 的生成器，同样可能泄漏 producer。
- 未调用真实模型、未修改业务库、未执行迁移、未手动重启/终止用户服务。用户已运行的 watch 模式会自行加载文件变化。

## 修复

1. 前端合并预览加载 effect。重挂载时不再把非零 generateTick 当成新命令；新点击才 force。语言、档案版本、级别与岗位变化请求服务端做新鲜度判断。
2. 单语普通稿/岗位定向稿按 profile、level、locale、job_id 分开查询；定向稿不再每次必生成，也不再误命中通用稿。定向稿用写手实际使用的 JobHints 哈希判断岗位上下文是否变更。双语两轨及组合稿透传岗位范围。
3. 无变化返回数据库已有草稿；渲染和审计仍会执行，不代表完全不发 HTTP 请求。显式 force、无草稿、档案版本/写作选项变化或模板 ID 不符时生成。
4. 用 AnyIO shield 等待 producer 退出及 DB finalizer 完成；预览 Response 在 send 异常时也显式关闭 iterator。编程错误不再伪装成 MySQL 断连反复 invalidate；真实 DBAPI 错误仍处理断连。
5. AgentKit 只配置了 structlog PrintLogger，JC 的标准 logging INFO 原先未输出。增加 JC 命名空间 handler，不打开第三方 SDK INFO。支持 JSON、trace 上下文、本地时间，重复配置不重复输出。
6. 增加 preview_cache 原因及 draft_id、preview_content 模式、原有 lifecycle 阶段日志；不打印 prompt / 简历正文。source_layout 是失败回退而非 AI 优化成功，保留既有警示。

## 验证

- 后端相关回归：148 passed，1 个既有测试夹具 Pydantic warning。
- 前端 Node：28 passed；TypeScript `tsc --noEmit` 通过。
- 隔离 Chromium，所有业务 API 返回夹具（零模型费用）：首次进入只发可复用请求；点击重新生成只产生一次 force=1；切走再进入（计数器仍非零）无强制生成；无 pageerror。React 开发 StrictMode 可重复挂载，故可出现两个可复用请求，不等于两次付费生成。
- 单元/集成覆盖：未变草稿 ID 复用且 writer 不重调；显式 force 和档案版本变化重建；中/英/双语岗位缓存隔离与岗位提示变化过期；真实 ASGI receive 断线与 send 失败时先停止 producer 再关闭 DB 依赖；AnyIO 已取消 scope 下的 driver cleanup；日志 INFO 输出及配置幂等。
- 本次不是生产模型或真实远端数据库端到端成功验收，不能保证历史失败全部由此原因造成。

## 排查入口

`api.log` 中查 `preview_cache`（hit / missing / forced / template_changed / profile_or_options_changed）、`preview_content`（generation mode）、`preview_lifecycle`（stage/status/elapsed_ms）。业务草稿依然存在数据库，不以本地日志作业务状态来源；本次无需新增表或迁移。
