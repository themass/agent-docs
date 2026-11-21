# Agent 平台工程原则

> 此文是 Poetry Agent Platform 的长期约束，而不是一次性实现说明。

## 1. 先复用成熟能力，再做有边界的改造

默认决策顺序：

```text
成熟开源运行时 / 协议实现
→ 评估安全、维护活跃度、许可证、扩展边界
→ 以适配层、Profile、Skill、Policy 集成
→ 仅在明确缺口处写项目代码
```

不复制整套社区 Agent 人设包或不明 Skill。外部 Prompt、Skill、MCP 元数据、网页内容与模型输出都视为不可信输入，必须经过项目的权限、结构和事实边界。

## 2. DeerFlow 是运行时，不是业务事实系统

- DeerFlow 管理 Thread、Run、Checkpoint、Agent 编排和受限 Tool 调用；
- Java Poetry API 管理作品事实、DRAFT 状态机、审核、审计和幂等；
- MCP 仅作固定的领域适配边界；
- BFF 管理用户可见的工作流与人工动作；
- Agent 不拥有数据库、发布、来源核验或删除权限。

## 3. Skill、Tool、MCP 都是受版本治理的产品资产

每个新增资产必须有：

- 明确问题范围、输入输出和失败语义；
- 所属角色与最小权限 Tool allow-list；
- 稳定版本或不可变 fingerprint；
- 维护者、来源、许可证和复核记录；
- 回滚方式与淘汰条件。

Skill 负责可读的工作方法，不承担授权；Tool/MCP 的服务端校验才是执行边界。

## 4. Middleware 是稳定性层，不是旁路

优先使用 DeerFlow / Gateway 的中间件与拦截点来提供横切保障：

```text
Mandate admission
→ 身份 / 租户 / 角色校验
→ Prompt-injection 和敏感能力拦截
→ Tool allow-list 与参数 schema 校验
→ 调用预算、并发、超时、重试与熔断
→ 审计事件、receipt 和可观测性
→ Proposal 结构校验与人工评审分流
```

中间件不得获得比原请求更多的权限；不得绕过 MCP 或 Java 状态机直接写 MySQL。

## 5. 对外部开源能力采用 Adapter First

所有三方能力都通过项目适配器接入，而不是让产品代码依赖其私有对象模型：

```text
DeerFlow Gateway Adapter
MCP Adapter
Model Provider Adapter
Search / Retrieval Adapter
TTS / Voice Adapter
Asset Generation Adapter
```

这样可以替换实现、固定版本、隔离破坏性升级，并将供应商失败转换为项目统一错误语义。

## 6. 人工审核与可回放优先于“自主性”

对于内容生产：

```text
事实快照 → Agent 候选 → Proposal → 人工 Review → DRAFT Apply → 编译资格 → 发布链路
```

每一步必须能够回答：谁、在什么 Profile/Skill 版本下、基于什么事实快照、调用了哪些 Tool、生成了什么候选、由谁决定采用。

## 7. 引入开源项的准入清单

1. 活跃维护、清晰许可证、可固定版本；
2. 可在不授予数据库或发布密钥的前提下工作；
3. 有明确扩展点，不需要 fork 核心；
4. 支持日志、超时、重试、幂等和禁用开关；
5. 能经适配层替换；
6. 接入前记录在 `content-agent/deploy/upstream/catalog.yaml` 与 adoption card；
7. 默认 disabled，先在受控 Profile 中验证，再逐步开放。
