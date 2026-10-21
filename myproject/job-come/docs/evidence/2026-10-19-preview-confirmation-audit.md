# 预览生成、真实进度与已确认原文保护验收

日期：2026-10-19（Asia/Shanghai）。仅测试夹具/临时 SQLite；未调用真实模型、修改业务库或重启本机服务。

## 已确认原因与修复

1. `ResumeStudio` 内联 `onBusyChange` 每次父组件渲染都会变化。`ElevatePreviewPanel` 重置 effect 依赖它，在请求中触发 abort；加载标志又阻止重试。改为 ref 持有回调，仅 profile/version/autoLoad 改变时重置。可选 resume-tracks 元数据异步刷新，不再阻塞预览请求或完成状态。
2. 原进度按等待秒数推进，不是后端执行证据。新增预览 SSE：`progress`、`result`、`error`，10秒心跳仅保活。五阶段是读取、生成、保存、渲染、检查；仅在对应真实操作返回后完成。双语子稿不得提前完成整个预览阶段。阶段计数不是 token 进度或精确工作量百分比。
3. 预览另调 writer，能覆盖已确认文案。使用现有 `jc_profile_patch_confirm` applied 记录计算请求内保护字段，不加表、不在本地保存业务状态。在构建、模型输出、排版重排及缓存归一化时保护原语言已确认的 summary / 经历与项目 highlights、scope、description。按实体 ID 或唯一身份匹配，不按模型数组位置猜测。当前值不再等于提议时尊重后续编辑。单条 highlight 确认后目前保守保护该实体整个 highlights 数组，避免重排索引错位。译文允许翻译；旧缓存修复持久化，避免仅显示层覆盖；双语旧缓存递归处理两轨。
4. 写手多模型 fallback 链可能超过代理/客户端预算。新增整链预算 `JC_PREVIEW_WRITER_TIMEOUT_SECONDS`（默认90秒，最大120秒）；整个 SSE 任务240秒，客户端255秒，Next代理300秒。写手失败时明确显示“AI 写作未完成”的原文排版预览，不冒充优化成功；降级采用 conservative 构建，禁止失败时悄悄增强职责。断开/超时取消并等待任务，数据库清理失败也须发送终止错误。
5. deterministic draft 未存 framing_emphases，缓存被一直判过期。补齐解析后选项戳，回归证明缓存不再重调 writer。
6. 不再直接截断 JSON 提示词；耗时构建/图片/渲染转线程。生成后检查档案版本，写手等待期间档案更新则拒绝保存旧结果。

## 数据语义与迁移

- 聊天解释不是简历字段，不自动全段写入 profile。确认卡片 patch 才是提交；保护用户批准且仍与当前 profile 一致的内容。
- 不保证 agent 提议必然与聊天解释完全一致；提议质量和生产网关成功率需独立观察。
- 本次不新增表。已有 `016_resume_draft_longtext` 将 sections/elevation_map 改为 MySQL LONGTEXT；尚未应用应在项目根运行 `./scripts/db_upgrade.sh`，否则大简历/照片仍可能保存失败。

## 验证

- 相关后端：**146 passed**，2个测试警告。真实 HTTP 确认、临时 SQL 持久化、mock writer、HTML 原文保护、旧缓存/双语保护、生成期间版本变化、超时取消、断线清理、rollback 失败、真实 SSE 路由均覆盖。
- 前端 Node：**27 passed**；`npx tsc --noEmit` 通过。
- 隔离 Chromium：所有业务 API 拦截为夹具，预览延迟800ms触发父组件重渲染，确认后验证新版本预览和逐字文字；通过，无 pageerror。这不是生产模型/数据库端到端验收。
- 扩大后端：**912 passed / 9 failed / 6 skipped**，不能宣称全绿：
  - 5个 PDF 和3个动态浏览器测试因共享 Python 环境未装 `playwright` 失败。Node Playwright 不等于 Python 包已安装。
  - `test_a_long_chain_reaches_every_endpoint_even_past_the_second_hop` 独立复跑仍失败：测试期待 a/b/c/c 四次，当前实际 a/b/c 三次。所有端点被访问，但重复调用次数断言不符；未为变绿而修改 routing 或断言。

## 边界

未执行用户业务库迁移，未发起付费模型调用。用户需自行重启前后端加载配置，之后验证真实业务链路。Python Playwright 与浏览器依赖仍未满足，不将此报告视为 PDF/动态浏览器全量验收通过。第三方模型、网络、存储仍可能失败；本次处理可诊断错误与显式降级，不保证模型永远成功。
