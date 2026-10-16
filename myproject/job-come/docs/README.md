# JC Engineering Documentation

本目录按软件团队的使用路径组织：**产品定义 → 系统设计 → 运行与测试 → 决策记录 → 调研 → 证据**。代码解释实现细节；本文档记录跨模块约定、接口、运行方式和“为什么这样设计”。

## Start here

| 你要做什么 | 从这里开始 |
|---|---|
| 理解 V1 做什么、服务谁、什么不做 | [`product/PRD-V1.md`](product/PRD-V1.md) |
| 了解 V1 之后的优先级 | [`product/PRD-ROADMAP.md`](product/PRD-ROADMAP.md) |
| 理解前后端、Agent、数据依赖与目录 | [`architecture/TECH-SYSTEM.md`](architecture/TECH-SYSTEM.md) |
| 修改或新增 API | [`architecture/TECH-API.md`](architecture/TECH-API.md) |
| 修改 Agent、Skill、Prompt 或 MCP | [`architecture/TECH-AGENT.md`](architecture/TECH-AGENT.md) |
| 修改简历优化写法、档位或审稿门禁 | [`architecture/TECH-RESUME-WRITING.md`](architecture/TECH-RESUME-WRITING.md) |
| 修改前端样式、组件类或设计令牌 | [`architecture/TECH-DESIGN-SYSTEM.md`](architecture/TECH-DESIGN-SYSTEM.md) |
| 处理数据库、Redis、TOS | [`architecture/TECH-DATA.md`](architecture/TECH-DATA.md) |
| 本地开发、运行服务 | [`operations/OPS-DEVELOPMENT.md`](operations/OPS-DEVELOPMENT.md) |
| 部署上线 | [`operations/OPS-DEPLOYMENT.md`](operations/OPS-DEPLOYMENT.md) |
| 运行测试或判断是否可发布 | [`operations/QA-TESTING.md`](operations/QA-TESTING.md) |
| 理解不可轻易推翻的技术选择 | [`decisions/`](decisions/) |

## Directory map

```text
docs/
├── product/          # PRD、产品范围、路线图
├── architecture/     # 系统、API、Agent、数据、LLM 技术设计
├── operations/       # 开发、部署、测试和发布门禁
├── decisions/        # ADR：已接受的架构决策及其取舍
├── discussions/      # 尚未冻结的调研与备选方案
├── evidence/         # 机器生成的验收/评测证据，不作为规范正文
```

## Documentation rules

1. **产品变化**写入 `product/`；**跨模块技术约定**写入 `architecture/`；**如何运行与验证**写入 `operations/`。
2. 选择难以逆转的框架、权限、数据或部署方案时，新建 `decisions/ADR-NNN-short-title.md`，不要把取舍埋在普通方案里。
3. 未定结论进入 `discussions/`，不能被实现或发布当作已确认要求。
4. API 字段契约以 OpenAPI/Pydantic schema 为准；文档说明稳定规则和业务语义，不复制易过期的 schema。
5. 每份规范文档都必须有状态与最后更新日期；不创建 `final`、`补充`、`最新版` 等并行副本。

## Naming

- `PRD-`：产品需求；`TECH-`：技术设计；`OPS-`：运行/部署；`QA-`：测试与验收；`ADR-`：已决策记录；`DISCUSSION-`：未定讨论。
- 文件夹表达受众与生命周期，文件前缀表达文档类型；两者结合，避免只靠文件名猜用途。
