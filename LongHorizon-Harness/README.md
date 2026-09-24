# LongHorizon-Harness — 设计文档（doc-sn）

> **性质**：学习用合成文档（中文）。权威仍是仓库 `README.zh-CN.md`、源码与测试。本目录不替代官方 README。  
> **2026-08-14** · 整理逻辑对齐 deepseek-harness/doc-sn：架构图 + **源码走读**。

---

## 语言与定位

| 项 | 内容 |
|----|------|
| 语言 | **Python ≥3.10**（包名 `lh-harness`） |
| 前端 | TypeScript / React（`frontend/`，Web Dashboard） |
| 产品命题 | **不训练模型、不替换 Agent**；在 Claude Code / Codex 等外层做 **Loop Engineering** |
| CLI | `lh-harness` → `lh_harness.cli:main` |

---

## 要看源码 → 先读这里

| 文档 | 覆盖 |
|------|------|
| **[source/README.md](./source/README.md)** | 索引 |
| **[source/01-manager-loop.md](./source/01-manager-loop.md)** | `manager.run` / `_run_impl` 四角色闭环、完成门禁、human gate |
| **[source/02-adapters-env-auditor.md](./source/02-adapters-env-auditor.md)** | `AgentAdapter` · `Environment` · `CommandAgentAdapter` · Auditor 解析 |
| **[source/03-supervisor-web.md](./source/03-supervisor-web.md)** | `RunSupervisor` · ControlBus · WebAPI 与 worker 边界 |

---

## 架构层（正文，不是目录）

| 文档 | 写了什么 |
|------|----------|
| [CORE_RUNTIME.md](./CORE_RUNTIME.md) | 公理、模块图、E2E 时序、权衡、与 DSH 对照 |
| [ARCHITECTURE_PART1.md](./ARCHITECTURE_PART1.md) | **详解** MEA 信息隔离、路由/完成门禁、human_gate、落盘三层、伪完成路径（含源码引用） |
| [ARCHITECTURE_PART2.md](./ARCHITECTURE_PART2.md) | **详解** Adapter 一集生命周期、Claude snapshot 只读、Auditor 管道、预算/信号、插件边界 |
| [ARCHITECTURE_PART3.md](./ARCHITECTURE_PART3.md) | **详解** CLI/Web 组装、Supervisor 证据模型、ControlBus 时序、评测与扩展食谱 |

---

## 建议阅读顺序

```text
1. CORE_RUNTIME §0–§2     命题与模块图
2. source/01              跟一次 round 的源码
3. source/02              Adapter 如何真正起 CLI
4. source/03              Web 如何管进程
5. PART1–3 按需
```

论文：[arXiv:2608.01964](https://arxiv.org/abs/2608.01964) · 主页：[lh-harness.pages.dev](https://lh-harness.pages.dev)
