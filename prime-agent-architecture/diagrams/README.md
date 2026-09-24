# Prime Agent Archify 图解

> `showcase` 质量档 · `meta.locale: zh-CN` · 共 **10** 张交互式 HTML

每张图有两个 HTML 路径：

- **规范名**（Archify `deliver` 输出）：`prime-agent-<topic>.<type>.html`
- **短别名**（文档链接用）：`prime-agent-<topic>.html`

| # | 规格 | 打开（短别名） | 规范 HTML | 类型 | 对应 GUIDE |
|---|------|----------------|-----------|------|------------|
| 1 | `prime-agent-stack.architecture.json` | [stack](./prime-agent-stack.html) | `prime-agent-stack.architecture.html` | architecture | §三/§五 全栈 |
| 2 | `prime-agent-turn.sequence.json` | [turn](./prime-agent-turn.html) | `prime-agent-turn.sequence.html` | sequence | §4.2 简化 |
| 3 | `prime-agent-e2e.sequence.json` | [e2e](./prime-agent-e2e.html) | `prime-agent-e2e.sequence.html` | sequence | §4.2 详版 |
| 4 | `prime-agent-rlm.sequence.json` | [rlm](./prime-agent-rlm.html) | `prime-agent-rlm.sequence.html` | sequence | §6.5 RLM |
| 5 | `prime-agent-jsonl.dataflow.json` | [jsonl](./prime-agent-jsonl.html) | `prime-agent-jsonl.dataflow.html` | dataflow | §6.2 JSONL |
| 6 | `prime-agent-cold-start.workflow.json` | [cold-start](./prime-agent-cold-start.html) | `prime-agent-cold-start.workflow.html` | workflow | §4.3 |
| 7 | `prime-agent-steer.workflow.json` | [steer](./prime-agent-steer.html) | `prime-agent-steer.workflow.html` | workflow | §6.4 steer/follow-up |
| 8 | `prime-agent-compaction.workflow.json` | [compaction](./prime-agent-compaction.html) | `prime-agent-compaction.workflow.html` | workflow | §6.6 |
| 9 | `prime-agent-dual-loop.architecture.json` | [dual-loop](./prime-agent-dual-loop.html) | `prime-agent-dual-loop.architecture.html` | architecture | §6.1 双环 |
| 10 | `prime-agent-goals.workflow.json` | [goals](./prime-agent-goals.html) | `prime-agent-goals.workflow.html` | workflow | §6.7 Goals |

## 重新生成

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
DIR=docs/prime-agent-architecture/diagrams

# 1. deliver 规范名 HTML
for f in "$DIR"/prime-agent-*.json; do
  [[ "$f" == *visual-check* ]] && continue
  type=$(python3 -c "import json; print(json.load(open('$f'))['diagram_type'])")
  base=$(basename "$f" .json)
  node "$ARCHIFY/bin/archify.mjs" deliver "$type" "$f" "$DIR/${base}.html" --quality showcase
done

# 2. 同步短别名（文档链接依赖）
cp "$DIR/prime-agent-stack.architecture.html"      "$DIR/prime-agent-stack.html"
cp "$DIR/prime-agent-turn.sequence.html"             "$DIR/prime-agent-turn.html"
cp "$DIR/prime-agent-e2e.sequence.html"            "$DIR/prime-agent-e2e.html"
cp "$DIR/prime-agent-rlm.sequence.html"              "$DIR/prime-agent-rlm.html"
cp "$DIR/prime-agent-jsonl.dataflow.html"            "$DIR/prime-agent-jsonl.html"
cp "$DIR/prime-agent-cold-start.workflow.html"       "$DIR/prime-agent-cold-start.html"
cp "$DIR/prime-agent-steer.workflow.html"            "$DIR/prime-agent-steer.html"
cp "$DIR/prime-agent-compaction.workflow.html"       "$DIR/prime-agent-compaction.html"
cp "$DIR/prime-agent-dual-loop.architecture.html"    "$DIR/prime-agent-dual-loop.html"
cp "$DIR/prime-agent-goals.workflow.html"            "$DIR/prime-agent-goals.html"
```
