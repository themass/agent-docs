# MetaGPT Archify 图解

> `showcase` 质量档 · `meta.locale: zh-CN` · 共 **8** 张交互式 HTML  
> 事实来源：[ARCHITECTURE.md](../ARCHITECTURE.md) · 文字总览（类图/循环/消息）：[CLASS_DIAGRAM_AND_RUNTIME.md](../CLASS_DIAGRAM_AND_RUNTIME.md)

| # | 层级 | 规格 | HTML | 类型 | 对应章节 |
|---|------|------|------|------|----------|
| 0 | Tier0 | `metagpt-core-domain.architecture.json` | [core-domain](./metagpt-core-domain.architecture.html) | architecture | [CLASS_DIAGRAM §2.0](../CLASS_DIAGRAM_AND_RUNTIME.md#20-核心领域总类图单图--2126-合并) 分层总类图 |
| 1 | Tier0 | `metagpt-four-layer.architecture.json` | [four-layer](./metagpt-four-layer.architecture.html) | architecture | §1.2 四层模型 |
| 2 | Tier0 | `metagpt-team-run.sequence.json` | [team-run](./metagpt-team-run.sequence.html) | sequence | §5 Team.run 外层循环 |
| 3 | Tier0 | `metagpt-role-react.sequence.json` | [role-react](./metagpt-role-react.sequence.html) | sequence | §6 observe/react 内层循环 |
| 4 | Tier1 | `metagpt-message-bus.dataflow.json` | [message-bus](./metagpt-message-bus.dataflow.html) | dataflow | §4.2–4.3 消息总线与 watch/cause_by |
| 5 | Tier1 | `metagpt-e2e-idea.sequence.json` | [e2e-idea](./metagpt-e2e-idea.sequence.html) | sequence | §7 端到端 idea → archive |
| 6 | Tier1 | `metagpt-environment-bus.sequence.json` | [environment-bus](./metagpt-environment-bus.sequence.html) | sequence | §4.2 Environment publish/run |
| 7 | Tier1 | `metagpt-sop-watch.workflow.json` | [sop-watch](./metagpt-sop-watch.workflow.html) | workflow | §4.3 cause_by / watch SOP 边 |
| 8 | Tier1 | `metagpt-rolezero.workflow.json` | [rolezero](./metagpt-rolezero.workflow.html) | workflow | §6.3 / §7.2 固定 SOP vs RoleZero |

## 图解说明

### Tier0 — 核心心智模型

1. **四层协作模型** — CLI → Team → Environment → Role → Action 主路径，Context 共享注入，ProjectRepo 产物落盘。
2. **Team.run 外层循环** — hire/invest → publish_message(idea) → n_round 内 env.run() 并行 tick → idle/预算检查 → archive。
3. **Role 内层循环** — msg_buffer → observe(watch 过滤) → _think/_act → Action.run() → publish_message。

### Tier1 — 深潜专题

4. **消息总线数据流** — AIMessage(cause_by) 经 Environment 路由到 msg_buffer，watch 过滤后触发 react()。
5. **端到端时序** — 用户 idea 经 MGXEnv/TeamLeader 派活，SOP 链 WritePRD → WriteDesign → WriteCode，最终 archive 到 ProjectRepo。
6. **Environment publish/run** — publish_message 路由、history 追加、env.run() 并行 tick 与 MGXEnv TeamLeader 派活。
7. **cause_by / watch SOP 边** — msg_buffer → watch 过滤 → memory → react → Action → publish 闭环订阅链。
8. **固定 SOP vs RoleZero** — use_fixed_sop 分支：watch 可预测链 vs TeamLeader + 命令工具默认路径。

## 重新生成

```bash
ARCHIFY=/Users/gqli/.cursor/skills/archify
DIR=docs/metagpt-architecture/diagrams
for f in "$DIR"/*.json; do
  case "$f" in *.visual-check.json) continue ;; esac
  type=$(python3 -c "import json; print(json.load(open('$f'))['diagram_type'])")
  base=$(basename "$f" .json)
  node "$ARCHIFY/bin/archify.mjs" deliver "$type" "$f" "$DIR/${base}.html" --quality showcase
done
```

## 验证

```bash
# 规格校验
node "$ARCHIFY/bin/archify.mjs" validate architecture "$DIR/metagpt-four-layer.architecture.json" --quality showcase

# 浏览器证据
node "$ARCHIFY/bin/archify.mjs" visual-check "$DIR/metagpt-four-layer.architecture.html" --json
```
