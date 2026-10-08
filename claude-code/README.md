# Claude Code / Agent SDK 文档

**SDK ↔ CLI 整体交互**（先读）：[SDK_CLI_INTERACTION.md](./SDK_CLI_INTERACTION.md)

进程拓扑、启动时序、同一根管道上的数据面/控制面、一次工具调用如何跨进程、session 与关闭。CLI Loop 是闭源侧的概念模型，SDK 是驱动它的可读层。

| 文档 | 读它干什么 |
|------|------------|
| [SDK_CLI_INTERACTION.md](./SDK_CLI_INTERACTION.md) | 两端怎么接在一起 |
| [CLAUDE_AGENT_SDK_GUIDE.md](./CLAUDE_AGENT_SDK_GUIDE.md) | Python SDK 源码：`query` / `Query` / `Transport` / JSONL |
| [CLAUDE_CODE_ARCHITECTURE_GUIDE.md](./CLAUDE_CODE_ARCHITECTURE_GUIDE.md) | 闭源 CLI：Loop、Hook、Skill、子 Agent、权限 |
| [CLAUDE_AGENT_SDK_ANALYSIS_SUMMARY.md](./CLAUDE_AGENT_SDK_ANALYSIS_SUMMARY.md) | 薄 SDK + 重 CLI，以及和 OpenAI Agents SDK 的对照 |
