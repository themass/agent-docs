# 目录与分包设计

日期：2026-11-14。描述 `server/src/companion/` 当前的形状，以及为什么是这个形状。

## 一句话

**按业务概念分包，不按技术层分包。** 一个概念的全部代码（领域规则、端口、用例、存储实现）
在同一个目录；模块之间只允许一个方向，**整个依赖图无环**。

## 演进过程

| 阶段 | 形状 | 问题 |
|---|---|---|
| 最初 | 按技术层切：`domain/ app/ adapters/ ports/ products/` | 改一个功能要进 4–5 个目录；找"记忆"要在 5 个地方翻 |
| 第二步 | 只把 `memory`/`voice` 收成模块，其余仍按层 | 两种形状并存 |
| 现在 | 29 个模块全部按业务概念切，层目录已删除 | — |

## 依赖图（无环）

按「入边数」从底向上排列。入边 = 有几个模块依赖它。

```
入边 16  store                                    ← 底座，出边 0
入边  7  memory        → store
入边  5  prompt        → lorebook, roles
入边  5  turn          → prompt, text
入边  5  util                                     ← 出边 0
入边  4  proactive     → room, store, text, turn
入边  4  roles         → lorebook, skills, store, util
入边  4  timeline      → store
入边  4  tools         → memory, proactive, store, timeline, util
入边  4  trace         → store
入边  3  account       → memory, store
入边  3  history                                  ← 出边 0
入边  3  persona       → memory, store
入边  3  room          → store
入边  3  skills                                   ← 出边 0
入边  3  text          → prompt
入边  3  uploads       → store, util
入边  2  auth                                     ← 出边 0
入边  2  avatar        → store, uploads
入边  2  brain         → prompt, tools, trace, turn
入边  2  chat          → history, jobs, memory, middleware, persona, prompt, roles, skills, store, turn, util
入边  2  compliance    → store
入边  2  jobs          → account, brain, history, memory, persona, proactive, store, timeline, tools
入边  2  lorebook                                 ← 出边 0
入边  2  voice         → text, trace
入边  1  api           → 17 个模块（路由层，最宽）
入边  1  llm                                      ← 出边 0
入边  1  middleware                               ← 出边 0
入边  0  bootstrap     → 24 个模块（组合根，最顶）
```

**叶子模块**（出边 0，不依赖任何东西）：`store`、`util`、`history`、`skills`、`auth`、
`lorebook`、`llm`、`middleware`。它们没有依赖，也最容易测。

**没有任何孤儿模块**：每个模块要么被别人依赖，要么依赖别人。

## 模块职责

### 入口与装配

| 模块 | 职责 |
|---|---|
| `api/` | HTTP / SSE / LiveKit 路由。只做参数解析与调用，不含业务规则 |
| `bootstrap/` | 组合根。选实现、接依赖。只有它与进程入口可以 import |

进程入口是包根上的 `serve.py`（API）、`worker.py`（语音）、`worker_jobs.py`（可选后台循环）。

### 对话主链路

| 模块 | 职责 |
|---|---|
| `chat/` | 回合引擎：提交、执行、排队排空、历史编辑、上下文组装、摘要重建 |
| `turn/` | 回合的形状：状态机（queue）、管线（pipeline，token 流 → 可朗读整句）、steering、控制面（Redis）、**主脑端口（brain_port）** |
| `brain/` | 主脑实现：DeerFlow、图内中间件、模型调用追踪。端口在 `turn/brain_port.py` |
| `memory/` | 记忆：召回、抽取、写入、管线、SQL 与内存实现 |
| `voice/` | 语音：TTS/STT 端口、火山与阿里实现、TTS 采集与质检 |
| `room/` | 语音房间：建房、入场 token、会话解析（`resolve.py`） |

### 内容与表达

| 模块 | 职责 |
|---|---|
| `prompt/` | 提示词组装（纯函数） |
| `roles/` | 角色卡与系统角色目录 |
| `persona/` | 用户画像 |
| `avatar/` | 形象包 |
| `lorebook/` | 世界书：条目、匹配、**按深度注入的结构（DepthInjection）** |
| `text/` | 断句、渲染、事件协议（纯逻辑） |
| `middleware/` | 输入侧安全检测（纯逻辑） |

### 后台与副作用

| 模块 | 职责 |
|---|---|
| `timeline/` | 事件时间线：抽取、存储、每日整理 |
| `proactive/` | 主动性：调度、开口、提醒、投递、推送 |
| `jobs/` | 后台任务队列：认领、执行、退避 |
| `tools/` | 工具：注册表、授权、确认、执行 |
| `trace/` | 质检留档：回合追踪、旁路写入、语音记录 |
| `uploads/` | 上传：校验、图片处理、对象存储 |
| `account/` | 账号注销 |
| `compliance/` | 合规：同意、导出、总开关 |

### 底座

| 模块 | 职责 |
|---|---|
| `store/` | 共享持久化：记录类型、端口、SQL 实现、表结构、队列状态约束 |
| `auth/` | 登录态校验（读 Java 写在 Redis 的 token） |
| `llm/` | 模型路由：场景 → 模型链（模型名只在 `.env`） |
| `skills/` | Skill 包加载 |
| `history/` | 历史窗口与摘要的纯函数 |
| `util/` | ULID 等无依赖工具 |

## 契约（4 条，`import-linter`）

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q   # 测试
PYTHONPATH=src .venv/bin/lint-imports          # 契约
```

| 契约 | 为什么 |
|---|---|
| 只有组合根与入口可以 import `bootstrap` | 依赖注入只在一处发生 |
| 业务模块不得依赖 `api` | 路由在模块之外，不能反过来被业务依赖 |
| 纯逻辑模块（`prompt`/`text`/`lorebook`/`middleware`/`util`）不得碰 I/O 与框架 | 这些要能在无数据库、无网络的测试里跑 |
| `store` 是底座，不依赖任何业务模块 | 持久化不反向依赖调用方（无需例外） |

模块内部（`model.py` / `port.py` / `service.py` / `sql.py` 之间）**允许互相依赖**，这是分包的意义。

契约的验证方式：不只跑一遍看是不是绿的，而是**注入违规代码**确认它会失败
（改 `domain` 引 `sqlalchemy`、让 `memory` 引 `api`、让 `memory` 引 `voice`，三次都 BROKEN）。

## 4 处双向依赖的拆法（已完成）

搬迁后曾有 4 个环，共同根因是「端口和实现住在一个模块」或「纯数据放在了上层」：

| 原环 | 根因 | 拆法 |
|---|---|---|
| `brain ↔ turn` | `BrainPort`/`TurnRequest` 描述回合的形状，却住在实现方 `brain` | 端口移到 `turn/brain_port.py` |
| `prompt ↔ roles` | `roles/profile` 为 `DepthInjection`/`ROLES` 两个常量反向依赖 `prompt` | 常量移到 `lorebook/model.py`（SillyTavern 的 depth prompt 语义） |
| `chat → jobs → proactive → chat` | `proactive/speaker` 用 `resolve_chat_session` 找会话 | 移到 `room/resolve.py`——"该用哪段会话"本来就属于房间 |
| `brain → tools → proactive → brain` | 随前两条一起消失 | 同上 |

收紧 `store` 契约时又抓到一处：`store/sql.py` 引 `turn/queue.QUEUE_TRANSITIONS`，
但 `turn/queue.py` 自己从不用它——它是 SQL 层的写入约束。→ 移到 `store/port.py`。

## 已知遗留

1. **`memory_hub` 是第二个顶层包**（`src/memory_hub/`），只被 `companion` 自己用。
   按需求保留（"未来还要做"）。
2. **`config.py` / `dburl.py` / `paths.py` 在包根**，不属于任何模块。
   `paths.py` 是唯一允许的布局知识；另两个是配置与连接串解析，放在包根合理。
3. **`prompt/plan.py` 的 `splice_injections` 触发 ruff UP047**（建议改用 PEP 695 泛型语法），
   基线就有，不是重构引入的。
