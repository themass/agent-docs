# 启动指令（三个项目）

整理于 2026-11-13。仓库里原来的情况：**没有任何启动脚本**，启动方式只零散写在文档里。现在
`companion-agent/run.sh` 是统一入口。

三个项目、四个要跑的东西：

| # | 项目 | 是什么 | 入口 |
|---|---|---|---|
| 1 | `companion-agent` | Python：agent 主脑、聊天/记忆/角色/语音接口 | `run.sh api` / `jobs` / `voice` |
| 2 | `testserverV` | Java Spring Boot：登录、拍照解题等 | `maven` |
| 3 | `myandroidTest` | Android App | `gradle` |

---

## 0. 一次性准备（companion-agent）

```bash
cd myproject/companion-agent
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env        # 填数据库、Redis、模型网关、LiveKit；密钥只放这里，不入库
```

`run.sh` 会在启动前把 `.env` 载入进程环境——适配器和 LiveKit CLI 读的是 `os.environ`，不读 `.env`，
只靠配置类读文件的话，音色和供应商会悄悄退回默认值。

---

## 1. 建表 / 升级结构

```bash
cd myproject/companion-agent && ./run.sh migrate
```

等于 `alembic upgrade head`。建 25 张 `ca_*` 表；LangGraph 的 4 张检查点表由服务启动时自建。
产品未上线，新表直接改 `0001_baseline`，不写增量迁移。

---

## 2. companion-agent 的三个进程

三者**各自独立启动**，用同一个 `.env`。

```bash
cd myproject/companion-agent && ./run.sh api
```
HTTP / SSE，默认监听 `127.0.0.1:8081`（`COMPANION_HOST` / `COMPANION_PORT` 可改）。手机 App 请求的是它。
**可多副本**，回合在接到请求的进程里跑。

```bash
cd myproject/companion-agent && ./run.sh jobs
```
后台任务进程。**必须单独跑一个**，它不接 HTTP，循环做：回合后写记忆/画像/时间线、会话摘要重建、
到期清理（含质检数据）、账号注销、用户设定的提醒到点发送、按时间线事件主动找用户。
**不跑它的后果是静默的**：聊天照常，但记忆不更新、提醒不响、主动消息不发、注销不执行，
任务只会堆在 `ca_agent_job` 表里。可多副本（靠数据库行锁 + Redis 抢占保证同一件事只做一次）。

```bash
cd myproject/companion-agent && ./run.sh voice
```
语音 worker，连 LiveKit，用户开语音时被派进房间。需要 `LIVEKIT_*`、`COMPANION_VOICE_ENABLED=true` 和火山凭据。
**它的 `.env` 必须和 API 指向同一个库、同一个 Redis、同一个模型网关**：语音回合走的是和文字同一个回合引擎，
指到不同地方，语音和文字就又变回两份互不相干的历史。
单进程同时接的房间数受 `COMPANION_VOICE_MAX_ROOMS`（默认 5，0 = 不限）限制，总容量 = 上限 × 进程数。

启动前检查（配置齐不齐、库和 Redis 连不连得上）：

```bash
cd myproject/companion-agent && ./run.sh check
```

写一个回合的追踪数据在远程库上约 17 秒（本机到库往返约 500ms），所以质检写入走后台队列，
不在回复路径上；队列满了会丢记录并计数，看 `trace_writer.stats.dropped`。

---

## 3. testserverV（Java）

```bash
cd testserverV && ./mvnw -q -DskipTests=true -pl vvv-link -am spring-boot:run
```

或者打包后运行：`mvn -DskipTests package`，再 `java -jar vvv-link/target/*.jar`。
模块：`vvv-common`、`vvv-link`、`vvv-poetry`、`vvv-roles`、`vvv-student`。配置在
`secrets.properties`（不入库，模板是 `secrets.properties.example`）。

注意：线上部署的 jar 里 `/api/roles/v1/*` 返回 400，原因是编译时缺 `-parameters`。角色列表已经由
companion-agent 提供，这个接口应当下线，不要再依赖它。

---

## 4. Android App

```bash
cd myandroidTest && ./gradlew :app:assembleChatDebug
adb install -r app/build/outputs/apk/chat/debug/app-chat-debug.apk
```

变体是 `chat`。服务端地址在 `Constants.BASE_IP`。装到真机后如果点安装弹窗，需要你自己确认（脚本不代点）。

真实设备测试集：

```bash
cd myandroidTest && python3 scripts/devicetest/companion_suite.py
```

---

## 5. 测试

```bash
cd myproject/companion-agent && ./run.sh test          # 不连外部服务的那批
./run.sh test -q -rf                                   # 同上，带失败摘要
```

需要 Redis 的那批（`test_api_routes`、`test_sessions`、`test_llm_record_e2e`）在没配
`COMPANION_TEST_REDIS_URL` 时会失败或跳过。本机没有 Redis 时可以用一次性实例：

```bash
T=$(mktemp -d) && redis-server --port 56390 --save "" --appendonly no --dir "$T" --daemonize yes --pidfile "$T/r.pid"
COMPANION_REDIS_URL=redis://127.0.0.1:56390/0 ./run.sh test
kill $(cat "$T/r.pid")
```

分级检查（分层契约）在 `companion-agent` 目录：

```bash
.venv/bin/lint-imports
```

---

## 6. 部署时必须注意的

- **公网网关没配。** `/v1` 在公网上是 404（nginx 没配 location），SSE 那条要 `proxy_buffering off`。
- **数据库连接数有上限。** 库 `max_connections=100`，已有别的服务在用。每个语音房间进程峰值占 6 条，
  1 个 API + 1 个后台进程时峰值最多 7 个房间，2 个 API 时只能 2 个。连接带 `application_name` 标签，
  用 `pg_stat_activity` 看真实占用。
- **`pgvector` 在这台库上不可用**，向量记忆召回做不了。
- **所有语音 worker 都满时**，用户进房间会听到静音：派不出 agent，而建房间接口还不知道容量，没法提前拒绝。
