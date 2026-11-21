# agent-authoring-service（第一阶段）

这是“诗词时空”下一模块：**受控内容生产 Agent**。它不是自由聊天机器人，而是把底座缺口整理成可审核的 DRAFT 提案，并把提案送入场景编译闸门。

## 目标

```text
只读 poetry_* → 缺口清单 → DRAFT 提案 →（可选）DRAFT API → facts 导出 → Scene Compiler
```

## 安全边界

- 只允许读取 `/Users/gqli/work/xuexi/poetry-agent-platform/content-agent/pipeline/tools/agent-draft/base-tools.mjs` 暴露的查询工具。
- 不提供 publish、retract、verify_source、set_verified、delete_content 能力。
- 生成内容默认 `DRAFT`，不能覆盖已发布版本。
- 编译器返回 `BLOCKED` 时，服务只输出阻塞原因，不绕过闸门。
- 本模块不接入真实 LLM；先固定编排、契约和审计边界，再接模型。

## 运行

```bash
node src/run-authoring.mjs --work work-chun-wang
node src/run-authoring.mjs --work work-chun-wang --facts /path/to/facts.json
node src/run-authoring.mjs --work work-chun-wang --submit --api http://localhost:8080
```

默认输出提案到 stdout；`--submit` 只调用 DRAFT API，不调用发布接口。
