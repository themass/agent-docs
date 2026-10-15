# Prime Agent 文档覆盖与改动记录（2026）

## 1. 范围与基线

本轮只修改 `docs/prime-agent-architecture/` 文档，源码只读核对 `prime-agent` Rust workspace HEAD `d592d5e7746408fe9097541af96d3239e263f7a1`。原有文档保留；TypeScript/Pi 时代内容作为 wire parity 与迁移背景，新增当前 Rust owner 映射。

## 2. 覆盖矩阵

| 主题 | 原有内容 | 本轮增加 |
|---|---|---|
| 总体架构 | Pi/Prime 双环叙述 | Rust 9 crate 依赖图与 Python runtime 边界 |
| Agent loop | `runAgentLoop` | `pa-agent::run_loop`、tool batch、steer/follow-up/continuation |
| Session | JSONL 树 | `SessionEngine`、append rollback/retained 语义、atomic write |
| Kernel | IPython/host.request | Rust kernel manager、Python pending futures、shutdown |
| Daemon | v7 协议 | supervisor/worker、backpressure、direct transport ticket |
| RLM | 高层叙事 | host request → core → child worker → ledger 的真实链路 |
| 缺口 | 泛化建议 | ownerClientId parity、pid reuse、partial replay 等源码证据 |

## 3. 新增和修改

- 新增 `SOURCE_DEEP_DIVE_2026.md`：12 章源码级架构、模块责任、代码解读和 10+ Mermaid 图。
- 新增本文件：证据矩阵、缺口、验证限制和改动摘要。
- 在现有 `ARCHITECTURE.md`、`ARCHITECTURE_GUIDE.md`、`ARCHITECTURE_REFERENCE.md`、`RUNTIME_BRIDGES.md`、`README.md` 和专题文档末尾追加入口与源码校准。
- 未删除历史内容，未修改 `prime-agent` 业务源码。

## 4. 重要发现

当前 Rust `peer_tickets.rs` 已明确披露：Rust 尚未移植 TS 对 `ownerClientId` 的 client-owned worker refusal。另一个需要验证的边界是 direct transport 使用 pid/socket identity，但源码注释说明尚未填充 TS process-start id；存在 pid reuse 风险，需要专项 parity 测试。

## 5. 验证结果与限制

- 原始文档保留检查、相对链接检查、Mermaid 围栏配对、`git diff --check`：已完成。
- 已通过源码路径、Rust/ Python 符号与 crate README 的静态核对。
- Cargo 未执行：当前环境没有配置 Rust default toolchain；未自动下载或安装工具链。
- Python 局部 unittest：`test_create_session` + `test_subagent_registry`，31 项通过。加入 `test_agent_message_skill` 后为 33 项、2 项 error，原因是旧 `packages/coding-agent/skills/agent-message/...` 路径不存在；没有修改测试源码掩盖错误。
- Mermaid 未实际逐图渲染，只检查围栏与本轮新增链接，不把静态检查称为渲染通过。
- 未运行真实 daemon 多进程、LLM、MCP OAuth、RLM child、Windows pipe、崩溃恢复和 parity binary comparison。


## 6. 文件级改动清单

| 文件 | 本轮追加内容 |
|---|---|
| README.md | 新增阅读目录、版本原则、后端阅读路线 |
| ARCHITECTURE.md | Rust 总体架构、三层状态、transcript/replay 区别 |
| ARCHITECTURE_GUIDE.md | 模块归属、真实类关系、persist_event 解读、故障排查顺序 |
| ARCHITECTURE_REFERENCE.md | 协议/队列/compaction 常量、JSONL 关系、持久化合同 |
| RUNTIME_BRIDGES.md | Rust/Python 时序、pending future 生命周期、direct transport 边界 |
| GOALS_AND_REFINE.md | Goal owner、预算边界、refine gates/cooldown/branch-version 流程 |
| EXTERNAL_ARTICLES_SYNTHESIS.md | 外部设计观点到当前实现的证据分级与验收合同 |
| SOURCE_DEEP_DIVE_2026.md | 12 章完整源码深读、迁移映射、带注释摘录、风险与验收矩阵 |
| COVERAGE_AND_CHANGES.md | 覆盖矩阵、重要发现、验证与交付记录 |

原有 7 个顶层 Markdown 均以修改前字节为完整前缀；`_archive/` 与既有 `diagrams/` 未改动。新增内容共有 19 个 Mermaid 围栏，含架构图、依赖图、类图、时序图、流程图、状态图与逻辑实体关系图。图中的概念节点与真实 struct/trait 已明确区分。

## 7. 可复现检查与后续工作

在源码的 `prime-agent-runtime/test` 目录运行（关闭 bytecode 写入，不修改源码）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../src python3 -m unittest test_create_session test_subagent_registry -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../src python3 -m unittest test_create_session test_subagent_registry test_agent_message_skill -q
```

文档检查包括原文 byte-prefix 保留、本轮新增相对路径存在、代码围栏成对与 scoped `git diff --check`。检查结束时源码工作区保持 clean。未提交 Git，也没有修改其他项目目录的既有改动。

建议下一轮先修复迁移路径测试，再配置 Rust toolchain 执行已有 goal/compaction/transport tests；针对 direct ticket 身份与 retained-write durability 补充故障注入。`tool_bridge.rs` 丢弃 `is_error` 是静态发现的适配风险，需真实工具输入输出验证后才能判定影响范围。
