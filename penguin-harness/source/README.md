# 附录 · 源码走读

> **阅读顺序第 9 步（可选）**  
> 先读：[术语表](../GLOSSARY.md) → [01](../01-项目介绍与设计思路.md)–[04](../04-关键场景详解.md) → [PART1](../ARCHITECTURE_PART1.md)。

## 怎么读（重要）

每篇统一：

```text
白话 → 代码 → 注释 → 本节小结 → … → 本章总结
```

对照打开：`packages/core/src/{engine,environment,agent,session,trace}/`

## 目录

| 文档 | 覆盖 | 读完应能回答 |
|------|------|--------------|
| [01-context-engine.md](./01-context-engine.md) | `context-engine.ts` | run / runTurn / steer / MergeQueue |
| [02-environment-tools.md](./02-environment-tools.md) | `environment.ts` + tools | 工具怎么执行与收尾 |
| [03-agent-session-trace.md](./03-agent-session-trace.md) | agent / session / trace | 组装、bootstrap、恢复 |

建议顺序：01 → 02 → 03。
