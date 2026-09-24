# Archify 全项目图解计划

> **工具**: Archify · **质量档**: `showcase` · **语言**: `zh-CN`

## 进度总览（2026-09-10）

| 项目 | 目录 | 已交付 | 状态 |
|------|------|--------|------|
| **Prime Agent** | [prime-agent-architecture/diagrams](./prime-agent-architecture/diagrams/) | **10** | ✅ P0 |
| **OpenCode** | [opencode-architecture/diagrams](./opencode-architecture/diagrams/) | **9** | ✅ P1 |
| **MetaGPT** | [metagpt-architecture/diagrams](./metagpt-architecture/diagrams/) | **8** | ✅ P1 |
| **OpenManus** | [openmanus-architecture/diagrams](./openmanus-architecture/diagrams/) | **8** | ✅ P1 |
| **Codex** | [codex-architecture/diagrams](./codex-architecture/diagrams/) | **9** + 1 早期 | ✅ P2 |
| **DeepTutor** | [deeptutor-architecture/diagrams](./deeptutor-architecture/diagrams/) | **8** | ✅ P2 |
| **OpenAI Agents SDK** | [openai-agents-architecture/diagrams](./openai-agents-architecture/diagrams/) | **5** | ✅ P3 |
| **agent-framework (MAF)** | [agent-framework-architecture/diagrams](./agent-framework-architecture/diagrams/) | **4** | ✅ P3 |
| **crewAI** | [crewai-architecture/diagrams](./crewai-architecture/diagrams/) | **4** | ✅ P3 |
| **grok-build** | [grok-build-architecture/diagrams](./grok-build-architecture/diagrams/) | **3** | ✅ P3 |
| **Hermes Agent** | [hermes-agent-architecture/](./hermes-agent-architecture/README.md) | **0** | 📋 P7 待建 |

**合计约 68 张** showcase HTML（含 visual-check sidecar；不含 legacy `design-thinking-series.html`）。

## 统一 Tier 模板

- **Tier 0**: stack architecture · e2e sequence · cold-start workflow  
- **Tier 1**: session dataflow · lifecycle · tool pipeline · compaction · queue · multi-agent  
- **Tier 2**: 项目特性（RLM / Message Bus / PlanningFlow 等）

## 流水线

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
node "$ARCHIFY/bin/archify.mjs" validate <type> <spec.json> --quality showcase --json
node "$ARCHIFY/bin/archify.mjs" deliver <type> <spec.json> <out.html> --quality showcase --json
node "$ARCHIFY/bin/archify.mjs" visual-check <out.html> --json
```

## 待续

- 各项目 toward **10 张** 的 Tier1 余量（MetaGPT / OpenManus / DeepTutor / OpenCode 各 +1~2）
- **agent-framework-checkpoint.lifecycle** 1440×900 visual-check 修复
- **Hermes Agent** — [FEATURE_DESIGN_CATALOG](./hermes-agent-architecture/FEATURE_DESIGN_CATALOG.md) 已整理；Archify 图解待建
- 各项目 README / ATLAS 嵌入图解链接
