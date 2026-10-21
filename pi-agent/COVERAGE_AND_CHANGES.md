# Pi 文档补充审计与改动摘要

## 1. 审计口径

2026-10-17 已将基线从本地 `1.2.0` 快照校正为官方 `v1.3.0` / commit `71023aec1546d6d677a65669c5665c0927ce0dd0`，重点核对入口、依赖方向、状态机、持久化和公开接口。没有把第三方插件仓库或网络最新版本当作已验证事实。

## 2. 现在覆盖的层次

| 层 | 主要文档 | 覆盖重点 |
|---|---|---|
| 全局架构 | `PI_SOURCE_DEEP_DIVE_2026.md` | 11 个 workspace 包、依赖、CLI/Durable 双路径 |
| Agent 算法 | 同上、`DESIGN_THINKING_SERIES.md` | outer follow-up、inner tool/steering、hooks、流式事件 |
| CLI 产品运行时 | `ARCHITECTURE.md`、`EXTENSIONS.md`、`RUNTIME_SERVICES.md` | AgentSession、SessionManager、扩展、cwd、trust |
| 后端运行时 | `BACKEND_RUNTIME.md` | mutation line、checkpoint、恢复、工具重放、JSONL/SQLite |
| 模型边界 | `RUNTIME_PROMPT.md`、`RUNTIME_SERVICES.md` | SystemMessage、sections、工具声明、认证和虚拟模型 |
| 会话与上下文 | `JSONL_TREE_GUIDE.md` | CLI session JSONL 与 Durable JSONL 的区别 |
| 分布式/远程 | `PI_SOURCE_DEEP_DIVE_2026.md` | Chord、env、MCP、Code Mode |
| 质量与界面 | 同上 | TUI、telemetry、evals |
| 源码导航 | `SOURCE_MAP.md` | 问题到入口、测试、阅读顺序 |

## 3. 本轮重点纠正的误读

1. 当前 CLI 路径是 `AgentSession -> agent-core Agent -> agent-loop -> pi-ai`；
2. Durable 是独立 Harness/TaskScheduler/GenerationTask 路径，不依赖 `agent-core` loop；
3. Chord 提供 Context/JSON/state/delta/replication；Session/Storage 在 durable；
4. CLI session JSONL 与 Durable JSONL 不是同一格式；
5. `beforeToolCall` 负责 block/reason/terminate，不任意替换参数/结果；
6. Durable 工具恢复只在存储与当前策略都安全时重跑，不能宣称 exactly-once；
7. JSONL 默认不 fsync，不能写成断电强持久；
8. project trust 不是完整 OS sandbox，QuickJS 也不自动提供 OS 隔离；
9. coding-agent telemetry 文件是安装遥测选择，不等于所有运行时 tracing。

## 4. 校验结果

- 新增源码级主指南、后端深潜、运行时支撑、源码导航和本审计页；
- 2026-10-17 对全目录 **73 张 Mermaid 图**使用 Mermaid 11.14.0 语法解析，错误为 0；
- 检查 **249 个本地链接/锚点**、**235 个固定到 v1.3.0 的源码链接目标**，错误为 0；后者根据实际下载的发布源码树验证，不冒充逐个 HTTP 请求测试；
- 保留原有专题与历史设计资料；本轮将错误结论/伪代码就地纠正，已移除实现就地标明历史边界；
- `git diff --check` 通过；当前字段 JSONL 示例逐行 JSON 与 parentId 结构检查通过（未做运行时导入测试）；
- 未运行 Pi 的完整测试、build 或真实 Provider/evals，因为本任务是文档整理，且这些操作可能产生网络/付费副作用。

## 5. 尚未声称的内容

- 没有逐个展开每个 Provider 适配器的全部字段；
- 没有重新验证第三方插件仓库的当前行为；
- Mermaid 做了语法校验，未做每张图的视觉渲染回归；
- “覆盖所有模块”按包级与关键源码入口理解，仍不等于逐文件逐行注释。

## 6. 2026-10-17 发布版核验与纠错

- 官方最新发布版确认为 v1.3.0，上一轮本地版本为 1.2.0；已改正文档基线，不再将两者混同。
- 新增 [VERSION_ALIGNMENT.md](./VERSION_ALIGNMENT.md) 和 [机器可读审计](./version-audit/2026-10-17.json)，记录官方发布时间、release/main commit、源码差异及 SHA-256。
- 重新清点发布源码，补齐 pi-ai 参数/投影/Provider、Durable SQLite、Chord output/ctx、交互 overlay 的变化。
- 已直接修正旧指南中的 leaf、工具 hook 和路径错误；整段已移除设计保留并在段首标为历史。此前“只追加”的记录是上一轮行为，本轮根据用户要求也替换错误表述，并非声称旧正文原样有效。
- Pi 源码链接固定到 v1.3.0；旧 HTML 也标为历史，避免另一条入口继续误导。main 未发布变化单列。

## 7. 后续建议

若继续深化，优先按 `SOURCE_MAP.md` 为每个 package 增加“入口—核心类型—关键测试—常见失败”四段式专题，并为 Provider、MCP transport、Chord wire、env frame protocol 分别补时序图和字段表。
