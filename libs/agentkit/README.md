# AgentKit — 公共组件包

| 项 | 内容 |
|---|---|
| PyPI 名 | `agentkit` |
| 路径 | `libs/agentkit/` |
| Python | 3.11+ |

**Agent 产品快速启动底座**：是复用组件，不是脚手架合集。每个模块的边界写在自己的
docstring 里，取舍和「什么不该放进来」也一起写在那儿。

设计文档：[docs/standards/公共组件包.md](../../docs/standards/公共组件包.md)

## 安装

```toml
dependencies = ["agentkit[metrics,llm]"]

[tool.uv.sources]
agentkit = { path = "../libs/agentkit", editable = true }
```

两个 extra 按需要装。**`metrics` 强烈建议装**：装了 `prometheus_client` 才有指标，
不装时 `agentkit.observability` 全部降级为 no-op、服务照常启动、`/metrics` 返回空——
一个「看起来正常但一条指标都没有」的部署，比装不上更难发现。

## 模块

| 模块 | 行数 | 内容 | 独立可用 |
|------|------|------|----------|
| `agentkit.observability` | 600+ | Prometheus 指标、方法埋点、JSON 快照、多服务聚合 | ✅ |
| `agentkit.llm` | 250 | 消息格式转换、按 token 计价 | ✅ |
| `agentkit.storage` | 110 | S3 兼容对象存储（TOS / OSS / MinIO） | ✅ |
| `agentkit.redis` | 59 | 连接工厂、服务端 session 存储 | ✅ |
| `agentkit.common` | 71 | trace_id 上下文、id 生成、structlog | ✅ |
| `agentkit.web` | 46 | FastAPI 工厂、TraceMiddleware、Actor 类型 | ✅ |
| `agentkit.adapters.deerflow` | 62 | DeerFlowSessionClient（唯一 import deerflow） | ⚠️ 接口占位 |
| `agentkit.mcp` | 16 | MCP tool 注册表 | ⚠️ 骨架 |

「独立可用」= 拿到别的项目里不需要改就能用。标 ⚠️ 的两项目前只有接口形状，
没有实现——别照着名字以为能用。

## 监控：三步接入

```python
from fastapi import Response
from agentkit.observability import CONTENT_TYPE, configure, render_metrics

configure(application="my-service", environment="prod")

@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE)
```

打点三选一：

```python
from agentkit.observability import method_metrics, record_llm_metrics, record_agent_phase

@method_metrics()                     # 记 Class.method 的耗时与成败
async def slow_thing(): ...

record_llm_metrics(scenario="coach", model="gpt-6-luna", duration=4.2,
                   status="success", prompt_tokens=1200, attempts=1)
record_agent_phase(phase="ttft", duration=8.1)
```

**多 worker 必须额外一步**，否则 `/metrics` 只反映其中一个 worker，而且看不出来。

这一步**只能用环境变量**，且必须在 python 启动前设好：

```bash
# 启动脚本里，import 之前
export PROMETHEUS_MULTIPROC_DIR=/var/tmp/my-service-metrics   # 目录必须本服务独占
```

```python
# 应用里只用来查询模式，不能用来开启
from agentkit.observability import MULTIPROCESS_MODE
assert MULTIPROCESS_MODE, "PROMETHEUS_MULTIPROC_DIR 没有在 import 前生效"
```

为什么不是一个 `enable_multiprocess(dir)` 函数：prometheus_client 在 **import 时**
就决定了计数器的存储方式（`prometheus_client/values.py`：
`ValueClass = get_value_class()`）。函数调用发生在 import 之后，改不了已经选定的类，
结果是**静默失效**——指标看起来正常，每个 worker 各算各的，抓一次只拿到一个 worker
的数字。本包曾提供过这样一个函数，它是坏的，已删除。

目录要在每次启动前清空：worker 被 SIGKILL 时不会调 `mark_process_dead`，残留的
`<type>_<pid>.db` 会永远累加进总数。`scripts/backend.sh` 里可以直接抄这个做法。

**多服务面板**：每个服务暴露 JSON 快照，由面板所在服务聚合。

```python
from agentkit.observability import snapshot, parse_peers, collect_peer_snapshots

@app.get("/metrics/snapshot", include_in_schema=False)
async def metrics_snapshot():
    return snapshot()

# 面板侧
peers = parse_peers("other=http://host:8000")     # "name=url" 逗号分隔
rows = await collect_peer_snapshots(peers, local=snapshot(), local_name="self")
```

三条设计约束，写在 `metrics.py` 里也靠测试钉住：

- **标签不取无界值。** 不带 user id、session id、异常文本——series 爆炸是指标后端
  最常见的死法。只允许 scenario / model / phase / status / 错误类名这类闭集。
- **记录绝不抛异常。** 指标失败不能影响它观察的请求。
- **「没有数据」不是 0。** 服务不可达时联邦结果里保留这一行并标 `ok=false`，
  而不是让它消失——消失的服务在面板上看起来和健康的一模一样。

## LLM

```python
from agentkit.llm import ModelPrice, parse_pricing, price_for, to_litellm_messages
```

只有两件事：把 LangChain 消息转成 OpenAI 线格式，和把「每百万 token 报价」算成
micro-USD。两个决定是有意的：**没有 token 数时报 `None` 而不是 0**（「不知道」和
「免费」不能在成本报表里长得一样）；**`openai/x` 和 `x` 两种写法都能查到同一个价**
（网关回显的是不带前缀的名字）。

路由（`routing.yaml` 场景、故障转移链、凭证）和审计落库**不在这里**——链的形状是
部署策略，审计存储是各服务自己的事。
