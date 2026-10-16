# TECH-AGENT：DeerFlow、Prompt、Skill 与 MCP

- **状态**：已确认的 V1 Agent 边界
- **最后更新**：2026-10-15

## 1. V1 方案

V1 采用 **vendored DeerFlow 源码 + 非 editable 安装**。上游源码固定在：

```text
/Users/gqli/work/deepagents/libs/agentkit/vendor/deer-flow/
```

生产依赖通过 [`../../scripts/install-production.sh`](../../scripts/install-production.sh) 执行：

```bash
uv sync --frozen --no-dev --no-editable
```

这让生产构建使用锁定源代码，而不是漂移的远程包版本。业务服务在 `backend/server/`，配置与可审查 Agent 资产在 `backend/agent/`。

## 2. 资产布局

```text
backend/agent/
├── deerflow/       # config.yaml、product_rules.md、extensions config
├── skills/         # public/ 自研能力；custom/ 审核后引入的外部能力
├── prompts/        # ingest、elevate、coach、export 等非 Agent prompt
├── llm/             # routing.yaml
└── litellm/         # LiteLLM 配置
```

DeerFlow 的运行态不写入项目根历史缓存，而写入：

```text
backend/server/.data/deerflow/runtime/
```

checkpoint 默认使用 SQLite（路径由 `JC_DEERFLOW_CHECKPOINT_*` 配置）；生产可根据并发与恢复需求评审专用持久化后端。

## 3. 权限与安全边界（不可放宽）

| 能力 | V1 策略 |
|---|---|
| 通用浏览器控制 | **不开放** |
| 通用网络访问 | **不开放** |
| 真实个人档案事实 patch | 模型不能自行确认；必须由用户一次性确认 |
| 数据库访问 | 不提供裸 SQL MCP；经业务服务和资源归属检查 |
| 文件访问 | 业务文件走 TOS/API；不向 Agent 暴露宿主机任意文件系统 |
| 外部 MCP | 默认关闭；按最小权限、白名单、审查和测试逐项启用 |

### 公开 JD 读取的例外

`jc_job_fetch` 是任务专用的受限工具，不是通用网络能力：仅允许白名单 skill 读取公开职位页；在请求前完成资源归属、DNS/IP/私网/重定向/体积/超时检查；禁止登录态、上传、点击、POST、任意请求头和任意方法。页面内容一律视为不可信输入，不能绕过档案确认规则。

## 4. Skill 与 MCP 责任分离

- **Skill**：定义可执行任务的指令、范围、输入输出和获准工具；例如简历辅导、JD 解析、模拟面试、真实题归档。
- **MCP tool**：服务端可验证的窄能力，统一以 `jc_*` 命名；实现用户身份、资源归属、输入校验与审计。
- **Prompt**：用于结构化解析、简历优化、审稿等确定性较强的模型调用，不应为此额外引入 Agent 循环。
- **API**：用户界面与外部调用的稳定边界；Agent 不能跳过 API/服务层直接触碰数据基础设施。

V1 的工具包括档案读取/提议变更、题库检索、面试归档、回答保存、JD 解析、匹配分析及受限 JD 读取。实际注册表以 `backend/server/src/jc/mcp/` 和 `backend/agent/deerflow/extensions_config*.json` 为准。

## 5. 变更检查清单

新增或修改一个 skill/tool 前，必须确认：

1. 是否确实需要 Agent，而非普通 API/Prompt；
2. 最小输入、输出、权限与可访问资源是什么；
3. 是否做了用户/资源归属校验、参数校验、限流与审计；
4. 是否会触及外部网络、文件、会议音频或敏感档案；
5. 是否已有覆盖成功、拒绝、越权、取消和失败恢复的测试；
6. 是否同步更新本文件与 [`../discussions/DISCUSSION-INTEGRATIONS.md`](../discussions/DISCUSSION-INTEGRATIONS.md) 的选型状态。
