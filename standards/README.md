# 工程标准索引

本目录存放 **跨项目可复用** 的工程原则、架构模板与启动清单。  
单个产品（如 JobCome）在 `docs/工程规范.md` 中 **继承 + 写覆盖表**，不重复全文。

---

## 文档

| 文档 | 用途 |
|------|------|
| **[PROJECT_STANDARD.md](PROJECT_STANDARD.md)** | 主标准 |
| **[公共组件包.md](公共组件包.md)** | **AgentKit** `libs/agentkit/` |
| [架构分层模板.md](架构分层模板.md) | 分层 |
| [观测与Trace标准.md](观测与Trace标准.md) | trace_id、Langfuse、LiteLLM、日志 |
| [新项目启动清单.md](新项目启动清单.md) | W0 前检查表 |

---

## 已采用的项目

| 项目 | 工程规范 |
|------|----------|
| JobCome | [job-come/docs/工程规范.md](../../job-come/docs/工程规范.md) |

---

## 新项目怎么用

1. 读 [PROJECT_STANDARD.md](PROJECT_STANDARD.md)
2. 复制 [新项目启动清单.md](新项目启动清单.md) 到项目 `docs/`
3. 新建 `docs/工程规范.md`，粘贴覆盖表模板并填写差异
4. 在 `AGENTS.md` 链接组织标准 + 本项目规范
