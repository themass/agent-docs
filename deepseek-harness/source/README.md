# 附录 · 源码走读

> **阅读顺序第 9 步（可选）**  
> 请先读完：[术语表](../GLOSSARY.md) → [01](../01-项目介绍与设计思路.md)–[04](../04-关键场景详解.md) → [PART1](../ARCHITECTURE_PART1.md)。

## 怎么读这些附录（很重要）

每篇统一四段式，避免「裸代码堆砌」：

```text
白话：这段在干什么
代码：仓库引用
注释：逐段/逐表解释
小结：这一节记住什么
……
章末：本章总结
```

对照打开：`packages/core/{agent-loop,agent,tools,session}/src/`。

## 目录

| 文档 | 覆盖源码 | 读完应能回答 |
|------|----------|--------------|
| [01-react-loop-agent.md](./01-react-loop-agent.md) | `agent-loop/src/agent.ts` | followup 之后谁醒、Turn/Step 怎么开停 |
| [02-tool-scheduler-runtime.md](./02-tool-scheduler-runtime.md) | `tool-calls.ts` + `tools` | 为何并行跑却按模型序写结果 |
| [03-session-inbox-factory.md](./03-session-inbox-factory.md) | session / inbox / 工厂 | 日志投影、收件箱、创建事务 |

建议顺序：01 → 02 → 03（与一次真实对话的数据流一致）。
