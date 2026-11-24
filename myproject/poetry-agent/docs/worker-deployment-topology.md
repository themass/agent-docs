# Worker 单独部署的网络拓扑（2026-11-24）

> 目标：把 `agent-worker` 从开发机的 compose 里拆出来，单独规划它落在哪台机、
> 开哪些口、谁能连它。规划依据是**代码实测**，不是 compose 注释的复述。
> 平台整体拓扑见 `deployment.md`；机器与域名实测见 testserverV
> `docs/poetry/network-architecture.md`。

## 1. 契约事实（先立住，后面的规则都从这里推）

`content-agent/agent/agent-worker/src/agent_worker/`：

| 事实 | 出处 | 对拓扑的含义 |
|---|---|---|
| 监听 `HOST` 默认 **`0.0.0.0:8102`** | `app.py:120` | 容器里默认对所有网卡开放，**边界必须由外部网络强制**，不能指望它自己绑 loopback |
| 入站只有两条写路由：`POST /internal/dispatch`（202）、`POST /internal/runs/{run_id}/cancel` | `app.py:97,107` | 都不是只读。**拿到 worker 就等于能发起内容生产轮次**（烧模型额度、产垃圾 DRAFT） |
| 两条写路由都要 `X-Poetry-Worker-Token`：令牌**已配**而请求没带/带错 → `401`；令牌**未配** → `503 worker token is not configured`（fail closed，`app.py:71-75`） | 同上 | 令牌是第二道，网络是第一道。别用「反正要令牌」当理由把 8102 发布出去；也别为了让 `/health/ready` 变绿而放宽它 |
| `/health/live`、`/health/ready` **无鉴权**；ready 里带 `worker_token_configured` 布尔 | `app.py:77-93` | 健康检查可以对监控开放，但它会泄露「令牌配了没」，所以监控源也要限 |
| 出站依赖只有两个：`POETRY_DOMAIN_CONTROL_URL`（默认 `http://poetry-domain-mcp:8101`）、`DEERFLOW_GATEWAY_URL`（默认 `http://deerflow-gateway:8001`） | `config.py:70-76` | worker **不直连 Java、不直连 MySQL、不持模型密钥**（compose 注释与 `.env.example` 一致：无 `POETRY_LLM_*`、无 `POETRY_DOMAIN_REVIEW_TOKEN`——A-05：agent 不能批准自己的提案） |
| compose 里 worker **只挂在 `poetry-agent-internal`（`internal: true`）**，不发布端口 | `compose.yaml` | 现状已经是「零公网出口」，单独部署要保持这条，而不是放宽 |

⇒ 一句话：**worker 是一个只需要两个内网对端、且必须被限制入站来源的进程。**

## 2. 目标拓扑

```
                      （公网：学生 / Studio 用户）
                                 │
                     网关 nginx  8.217.122.83     ← 只有 80/443
                                 │
        ┌────────────────────────┴───────────────────────┐
        │                                                │
  应用机 64.32.22.150 (==104.160.191.87)          agent 机（worker 落这里）
  vvv-link jar :8888                              ┌──────────────────────────┐
  vvv-poetry / vvv-student                        │ poetry-agent-internal     │
        ▲                                         │   agent-worker  :8102     │
        │ 只有 mcp 与 bff 能到 Java（私有路径）    │   poetry-domain-mcp :8101 │
        └─────────────────────────────────────────│   deerflow-gateway :8001  │
                                                  │   redis :6379             │
        agent 机只有 22 + 443 对公网开            │   （internal 网无默认路由）│
        8100/8101/8102/8001 一律不对公网          └──────────────────────────┘
```

要点：

1. **worker 与 `poetry-domain-mcp` 必须同机或同私网**。worker 只认 `POETRY_DOMAIN_CONTROL_URL`
   这一个写通道；把 mcp 放到别处而跨公网连接，等于把「能应用 DRAFT 的控制桥」搬到公网上——
   compose 里那个「No `ports:` on purpose」的注释（A-18）就是为了防这件事。
2. **worker 所在网络不能有默认路由**。compose 的 `internal: true` 就是这件事；单独部署时
   要么保持 compose（单机 docker + 一张 internal 网），要么用云安全组把 worker 那台机的
   出站全禁（只留到 mcp/gateway 的对端安全组）。模型调用只发生在 `deerflow-gateway`，
   worker 不需要出门。
3. **入站只允许 mcp/bff/编排器**。worker 的两条写路由没有来源校验，只有令牌校验；
   网络层必须补上 `src` 限制。
4. **8100（BFF/Studio）不在 worker 拓扑里**。BFF 是人用的写入口，今天没有进程，
   将来也只走 SSH 隧道或私网，不给公网域名（见 testserverV `docs/poetry/agents.md`）。

## 3. 单机部署形态（推荐先按这个做，最小改动）

保持 compose 不变，只加两件东西：`worker` 单独一个 profile，以及一张 host 侧防火墙规则。

```bash
# 在 agent 机上：只起 worker + mcp（不起 BFF、不起 gateway/redis），点名起服务
docker compose -f compose.yaml -f compose.worker.yaml up -d agent-worker poetry-domain-mcp

# 合并结果对不对，先看这两条（不启动任何东西）
docker compose -f compose.yaml -f compose.worker.yaml config --services
docker compose -f compose.yaml -f compose.worker.yaml config | grep -A3 "ports:"
```

第二条是**上线前必查**：合并后 `agent-worker` / `poetry-domain-mcp` 底下不应出现任何 `ports:`。
overlay 文件 `content-agent/deploy/compose.worker.yaml` 只做两件事——`restart: unless-stopped`
与资源上限（并发由 `WORKER_MAX_CONCURRENT_RUNS` 管），不引入端口。

| 端口 | 谁可连 | 怎么实现 |
|---|---|---|
| `8102` worker | 只有同 compose 内的 mcp/bff（容器网络内），**不发布到 host** | compose 不写 `ports:`（已如此） |
| `8101` mcp | 只有 internal 网内容器 | 同上（已如此）；**且** host 防火墙再兜一层 |
| `8001` gateway | internal 网 | 同上 |
| `6379` redis | internal 网 | 同上，另设 `requirepass` |
| `8888` Java（应用机） | 只有 agent 机的 mcp/bff | **应用机侧**安全组：`src = agent 机 IP`（这也是端口收紧那件事的一部分） |

⚠ **两个已实测的坑**：

- `POETRY_API_BASE_URL` 现在如果填公网地址（`http://64.32.22.150:8888/...`），
  那么 mcp → Java 这条内网依赖会绕出去再绕回来，**而且依赖那台机的 8888 暴露在公网**。
  填私网/同机地址，并等应用机把 `:8888` 收成只允许网关 + agent 机（见
  testserverV `docs/poetry/network-architecture.md`「三个暴露问题」）。
- `worker_token` 没配时 worker **拒绝所有写请求**（`app.py:72-73`），`/health/ready` 报
  `not_ready`。这是有意的 fail closed，别为了让健康检查绿而放宽。

## 4. 什么时候才需要「worker 独立成一台机」

按现在的内容生产节奏（一周一首的量级），**不需要**。worker 的并发由
`WORKER_MAX_CONCURRENT_RUNS`（默认 2）限住，单轮成本是模型调用而不是本机 CPU。
值得拆出去只有两种信号：

1. 一轮 run 里出现长任务（大批量 gap-report、多首并发生成）导致 agent 机上
   BFF/Studio 卡顿；
2. 需要给 worker 独立的出站白名单审计（合规/成本归因）。

真要拆时，最小正确形状是：新 agent 机 → 私网对等 → 只放行
`8101/8001/6379` 来自旧 agent 机，`8102` 仍不发布；mcp 留在原机（它是唯一 Java 出入口，
少动一处少一处风险）。

## 5. 验证清单（部署后你自己跑，我不碰机器）

```bash
# a) 8102 不应对公网可达（在你的笔记本上跑，应超时/拒绝）
curl -m 6 -o /dev/null -w "%{http_code}\n" http://<agent 机 IP>:8102/health/live

# b) 容器内应可达（在 agent 机上）
docker compose exec agent-worker python -c \
  "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8102/health/live').status)"

# c) 无令牌必须 401（证明第二道也在）
docker compose exec poetry-domain-mcp python -c \
  "import urllib.request as u;u.urlopen(u.Request('http://agent-worker:8102/internal/dispatch',method='POST'))" \
  2>&1 | grep -o "401"

# d) worker 不应能出网（internal 网无默认路由）
docker compose exec agent-worker python -c \
  "import urllib.request;urllib.request.urlopen('http://example.com',timeout=4)" 2>&1 | tail -1

# e) mcp 不应能出到公网 8101（在别的机上跑，应超时）
curl -m 6 -o /dev/null -w "%{http_code}\n" http://<agent 机 IP>:8101/internal/health
```

(d) 失败（连不上）才是**正确结果**。(c) 得到 401 才算令牌生效。
`content-smoke` 只覆盖 BFF↔mcp 的连通，不覆盖 a/d/e 这三条边界——**单独部署时必须补跑这三条**，
因为它们才是把「不发布端口」从约定变成事实的检查。
