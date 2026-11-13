# 目录与分包设计

日期：2026-11-14。描述 `server/src/companion/` 当前的形状，以及为什么是这个形状。

## 一句话

**按业务概念分包，不按技术层分包。** 一个概念的全部代码（领域规则、端口、用例、存储实现）
在同一个目录；模块之间只允许一个方向。

## 演进过程

| 阶段 | 形状 | 问题 |
|---|---|---|
| 最初 | 按技术层切：`domain/ app/ adapters/ ports/ products/` | 改一个功能要进 4–5 个目录；找"记忆"要在 5 个地方翻 |
| 第二步 | 只把 `memory`/`voice` 收成模块，其余仍按层 | 两种形状并存，读代码要先判断"这个在哪种里" |
| 现在 | 29 个模块全部按业务概念切 | 层目录清空（`domain/`、`app/`、`adapters/`、`ports/`、`products/` 已删除） |

## 模块清单

### 入口与装配

| 模块 | 职责 | 出边 |
|---|---|---|
| `api/` | HTTP / SSE / LiveKit 路由。只做参数解析与调用，不含业务规则 | 18 |
| `bootstrap/` | 组合根。选实现、接依赖。**只有它与进程入口可以 import** | 24 |

进程入口是包根上的三个文件：`serve.py`（API）、`worker.py`（语音）、`worker_jobs.py`（可选的后台循环）。

### 对话主链路

| 模块 | 职责 |
|---|---|
| `chat/` | 回合引擎：提交（submit）、执行（turn_runner）、排队与排空（drain）、历史编辑（history）、上下文组装（context/assembler）、摘要重建、停机排空 |
| `turn/` | 回合的状态与形状：状态机与处置规则（queue）、管线（pipeline，token 流 → 可朗读整句）、steering、触发器、控制面（Redis，跨进程协调） |
| `brain/` | 主脑：`port.py` 是接口，`deerflow.py` 是 DeerFlow 实现，`graph_middleware.py` 是图内中间件，`llm_trace.py` 采集模型调用 |
| `memory/` | 记忆：召回（recall/recallers）、抽取（extraction）、写入（recorder）、管线（pipeline）、SQL 与内存实现 |
| `voice/` | 语音：TTS/STT 端口、火山与阿里实现、TTS 采集（tts_capture）与质检（tts_accuracy/tts_archive） |
| `room/` | 语音房间：建房、入场 token、会话绑定 |

### 内容与表达

| 模块 | 职责 |
|---|---|
| `prompt/` | 提示词组装，纯函数 |
| `roles/` | 角色卡（SillyTavern V2）与系统角色目录 |
| `persona/` | 用户画像：从事实与对话归纳"这个人的样子" |
| `avatar/` | 形象包 |
| `lorebook/` | 世界书：按关键词激活的设定条目 |
| `text/` | 断句、渲染、事件协议（纯逻辑） |
| `middleware/` | 输入侧安全检测（纯逻辑） |

### 后台与副作用

| 模块 | 职责 |
|---|---|
| `timeline/` | 事件时间线：抽取、存储、每日整理 |
| `proactive/` | 主动性：调度、开口、提醒、投递、推送 |
| `jobs/` | 后台任务队列：认领、执行、退避 |
| `tools/` | 工具：注册表、授权、确认、执行 |
| `trace/` | 质检留档：回合追踪、旁路写入、语音记录存储 |
| `uploads/` | 上传：校验、图片处理、对象存储（TOS / 内存） |
| `account/` | 账号注销：跨存储删除 |
| `compliance/` | 合规：同意、导出、主动消息总开关 |

### 底座

| 模块 | 职责 | 入边 |
|---|---|---|
| `store/` | 共享持久化：会话/消息/队列/角色/上传/确认的 SQL 实现与表结构 | **14**（被依赖最多） |
| `auth/` | 登录态校验（读 Java 写在 Redis 的 token） | 2 |
| `llm/` | 模型路由：场景 → 模型链（模型名只在 `.env`） | 1 |
| `skills/` | Skill 包加载 | 3 |
| `history/` | 历史窗口与摘要的纯函数 | 3 |
| `util/` | ULID 等无依赖工具 | 5 |

## 依赖关系

```
                    ┌─────────────┐
                    │  bootstrap  │  组装一切
                    └──────┬──────┘
                    ┌──────┴──────┐
                    │     api     │  路由
                    └──────┬──────┘
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
   │  chat   │        │  jobs   │        │proactive│
   └────┬────┘        └────┬────┘        └────┬────┘
        │                  └───────┬──────────┘
   ┌────┴────┬─────────┬───────────┴────┐
   │  brain  │  roles  │  tools  │ turn │
   └────┬────┘         └────┬────────────┘
   ┌────┴──────────────────┴──────────────┐
   │ memory  persona  prompt  timeline    │
   │ voice   avatar   text    uploads     │
   │ trace   compliance  account  voice   │
   └──────────────────┬───────────────────┘
              ┌───────┴────────┐
              │     store      │  底座（入边 14）
              │ auth llm skills│
              │ history util   │
              └────────────────┘
```

数字（出边 = 它依赖几个模块，入边 = 几个模块依赖它）：

| 模块 | 出 | 入 | 模块 | 出 | 入 |
|---|---|---|---|---|---|
| `bootstrap` | 24 | 0 | `store` | 2 | **14** |
| `api` | 18 | 1 | `memory` | 1 | 7 |
| `chat` | 12 | 3 | `brain` | 4 | 6 |
| `jobs` | 9 | 2 | `turn` | 2 | 6 |
| `proactive` | 5 | 4 | `util` | 0 | 5 |
| `roles` | 5 | 4 | `prompt` | 2 | 5 |
| `tools` | 5 | 4 | `timeline` | 1 | 4 |

## 契约（4 条，`import-linter`）

守的是**模块之间的方向**，不是模块内部的形状。

| 契约 | 为什么 |
|---|---|
| 只有组合根与入口可以 import `bootstrap` | 依赖注入只发生在一处；否则每个模块都能拿到全局装配，测试没法替换 |
| 业务模块不得依赖 `api` | 路由在模块之外。反过来的话，改一个接口就要动业务代码 |
| 纯逻辑模块（`prompt`/`text`/`lorebook`/`middleware`/`util`）不得碰 I/O 与框架 | 这几块要能在没有数据库、没有网络的测试里跑（断句、提示词、世界书匹配都是纯计算） |
| `store` 是底座，不依赖任何业务模块 | 持久化不该反向依赖调用方（例外见下） |

模块内部（`model.py` / `port.py` / `service.py` / `sql.py` 之间）**允许互相依赖**，这是分包的意义。

## 已知的双向依赖（未拆）

4 处真的双向。没有靠放宽契约掩盖，也没有硬拆——每一条的拆法都要改接口，属于下一轮。

| 环 | 具体的边 | 拆法 |
|---|---|---|
| `brain <-> turn` | `turn/pipeline` 用 `brain/port` 的 BrainPort；`brain/deerflow` 用 `turn/conversation` 的 `lc_user_id`、`turn/steer` 的渲染 | 把 `lc_user_id` / steer 渲染抽到底层（`text` 或 `util`） |
| `prompt <-> roles` | `prompt/roleplay` 用 `roles/profile` 的 RoleProfile；`roles/profile` 用 `prompt/plan` 的 ROLES 常量 | RoleProfile 下沉，或 plan 常量下沉 |
| `chat <-> jobs <-> proactive` | `chat/history` 用 `jobs/port` 的 JobStore；`jobs/background` 装配 proactive；`proactive/speaker` 用 chat 提交回合 | JobStore 端口下沉到 `store`；proactive 只依赖 `turn/port` |
| `brain -> tools -> proactive -> brain` | `brain/deerflow` 用 tools 的工具声明；`tools/runtime` 用 proactive 的投递；`proactive` 用 brain 说话 | 投递下沉到独立模块 |

## 已知的遗留

1. **`store` 反向依赖两处**：`store/sql.py` 引 `uploads/service` 的 `UploadRecord`（函数内 import），
   `store/port.py` 定义 `UploadStore`。契约里给了例外；正确做法是把 `UploadRecord` 下沉到 `store`。
2. **两个端口文件**：`proactive/reminders_port.py` 和 `proactive/reminders_domain.py` 是搬迁时
   为了避免命名冲突起的名字，语义上该叫 `port.py` / `model.py`。
3. **`memory_hub` 是第二个顶层包**（`src/memory_hub/`），只被 `companion` 自己用。
   用户要求保留（"未来还要做"）。
4. **`config.py` / `dburl.py` / `paths.py` 在包根**，不属于任何模块。`paths.py` 是唯一允许的
   布局知识；另两个是配置与连接串，放在包根合理。
