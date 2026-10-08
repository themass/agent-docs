# Codewhale 图解索引

| 文档 | 内容 |
|------|------|
| [DIAGRAM_ATLAS.md](./DIAGRAM_ATLAS.md) | **全局**：五层架构、E2E Turn、核心类图、ER、Op/Event |
| [AGENT_MODULE_DIAGRAMS.md](./AGENT_MODULE_DIAGRAMS.md) | **模块级**：每个 Agent 相关 crate/模块一张及以上图（CW-01…CW-29 + 附录） |

重新生成模块图集：

```bash
python3 docs/scripts/generate_agent_module_diagrams.py
```

交互式 HTML（可选，对标 codex `diagrams/`）：需 Archify，规格待补。
