# JobCome

独立 Web：拔高简历、练手攻目标、面试库渐进提升。不代投递。

NaviForge 是另一个浏览器插件项目，与本产品无关。

## 简历主线（当前收束方向）

`/resume-agent` 按 **左编辑核对 → 中拔高预览 → 右 Agent** 三栏工作台交付：

1. 上传解析（需 `JOB_COME_LLM_ENABLED=true` + `YUAI_API_KEY`）
2. 左侧结构化编辑 + **确认档案**
3. 中间拔高预览 + `elevation_map` 变更对比
4. 右侧 Agent 多轮改稿
5. 登录后导出 PDF/Word

启动开发（默认每次清 `.next` 避免缓存损坏；保留缓存用 `JOB_COME_WEB_CLEAN=false`）：

```bash
./scripts/dev.sh
# 或显式清缓存
JOB_COME_WEB_CLEAN=true ./scripts/dev.sh
```

# DeerFlow harness only (see docs/DeerFlow接入.md)

- **第一版（M1）功能与方案**：[docs/M1-第一版方案.md](docs/M1-第一版方案.md) ← **开工读这份**
- **MySQL 库表（前缀 `jc_`）**：[docs/数据库设计.md](docs/数据库设计.md)
- **TOS / CDN / LiteLLM**：[docs/基础设施与LLM.md](docs/基础设施与LLM.md)
- **组织工程标准（可复用）**：[docs/standards/PROJECT_STANDARD.md](../docs/standards/PROJECT_STANDARD.md)
- **工程规范（JobCome）**：[docs/工程规范.md](docs/工程规范.md)
- **Trace / Langfuse**：[docs/可观测性与Trace.md](docs/可观测性与Trace.md)
- **前端架构 / 登录态**：[docs/前端架构与鉴权.md](docs/前端架构与鉴权.md)
- 全貌与长期计划：[docs/路线图.md](docs/路线图.md)
- **Agent 底座（DeerFlow Skill/MCP）**：[docs/DeerFlow-Agent底座.md](docs/DeerFlow-Agent底座.md)
- 产品设计：[docs/产品设计.md](docs/产品设计.md)
- MVP 产品方案：[docs/MVP-产品方案.md](docs/MVP-产品方案.md)
- 技术方案：[docs/技术方案.md](docs/技术方案.md)
- MCP 配置模板：[deploy/deerflow/extensions_config.example.json](deploy/deerflow/extensions_config.example.json)
