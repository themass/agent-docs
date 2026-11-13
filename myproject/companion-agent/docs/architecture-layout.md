# 目录与分包设计

日期：2026-11-14。描述 `server/src/companion/` 的形状。

## 一句话

**两层：`agent/` 是可复用的能力，`service/` 是这个产品的业务流程。依赖只允许 `service → agent`。**

## 为什么这样切

上一版按业务概念拉平（`chat`、`memory`、`lorebook` 并排），解决的是"改一个功能只进一个目录"，
但回答不了"哪些是 agent、哪些是服务"——目录里没有这条线。

这一版按**能不能被别的产品拿去用**来切：

- `agent/` 不认识"角色扮演"这个产品。换一个产品（招聘 agent、客服 agent）时，整层拿走。
- `service/` 是这个产品的流程：一个用户和一个角色怎么对话、语音怎么进同一个会话、什么时候主动开口。

## 结构

```
src/companion/
├── agent/                     可复用能力（不依赖 service）
│   ├── brain/                 主脑端口（port.py）+ DeerFlow 实现 + 图内中间件 + 模型调用采集
│   ├── memory/                记忆：召回、抽取、写入、SQL 与内存实现
│   ├── tools/                 工具框架：注册表、授权、确认、执行
│   ├── roles/                 角色卡与角色目录的解析（纯逻辑）
│   ├── prompt/                提示词组装、RoleProfile（纯函数）
│   ├── lorebook/              世界书：条目、匹配、按深度注入
│   ├── text/                  断句、渲染、事件协议（纯逻辑）
│   ├── middleware/            输入侧安全检测（纯逻辑）
│   ├── skills/                Skill 包加载
│   ├── llm/                   模型路由（场景 → 模型链）
│   └── util/                  ULID
│
├── service/                   本产品的业务流程
│   ├── chat/                  回合引擎：提交、执行、排队排空、历史、摘要
│   ├── turn/                  回合状态机、控制面、触发器
│   ├── turns/                 把输入接到提交路径（语音、主动开口）
│   ├── voice/                 语音：TTS/STT、火山与阿里实现、TTS 采集与质检
│   ├── room/                  语音房间：建房、入场 token、会话解析
│   ├── proactive/             主动性：调度、开口、提醒、投递
│   ├── timeline/              事件时间线
│   ├── jobs/                  后台任务队列
│   ├── tools_impl/            产品工具（recall_facts / create_reminder …）
│   ├── roles/                 角色来源与解析（文件、用户自建）
│   ├── persona/               用户画像
│   ├── avatar/                形象包
│   ├── trace/                 质检留档
│   ├── uploads/               上传
│   ├── account/               账号注销
│   ├── compliance/            合规
│   ├── auth/                  登录态校验
│   └── history/               历史窗口与摘要的纯函数
│
├── db/                        共享持久化：表结构、记录类型、端口、SQL 实现
├── api/                       HTTP / SSE / LiveKit 路由
├── bootstrap/                 组合根
├── config.py  dburl.py  paths.py
└── serve.py  worker.py  worker_jobs.py     进程入口
```

## 依赖方向

```
        bootstrap  ──▶  api  ──▶  service  ──▶  agent  ──▶  db
                        │          │            │
                        └──────────┴────────────┴──▶  db / util / config / paths
```

`agent/` 内部各模块之间可以互相依赖（`brain → prompt → lorebook`、`text → prompt`、`tools → memory`）。
`service/` 可以依赖 `agent/` 的任何部分，**反向一律禁止**。

## 契约（6 条，`import-linter`）

| 契约 | 为什么 |
|---|---|
| `agent` 不得依赖 `service` | agent 要能被别的产品直接拿走 |
| `agent` 不得依赖 `api` 与 `bootstrap` | 同上；组合与协议不属于能力 |
| `agent` 的纯逻辑部分（prompt/text/lorebook/middleware/util）不得碰 I/O 与框架 | 这些要能在无库无网的测试里跑 |
| `db` 不依赖任何业务层 | 持久化不反向依赖调用方 |
| `service` 不得依赖 `api` | 路由在业务之外 |
| 只有组合根与入口可以 import `bootstrap` | 依赖注入只在一处发生 |

**这些契约是有效的，不是摆设**：这一轮写完后它们立刻抓到 10 条真实越界
（`brain → turn`、`prompt → roles`、`tools/builtin → proactive/timeline` 等），逐条修掉的。

## 边界怎么划的（几个容易搞错的）

| 东西 | 归属 | 理由 |
|---|---|---|
| `BrainPort` / `TurnRequest` / `TurnRefused` | `agent/brain/port.py` | 描述"一次模型回合"的形状，任何 agent 产品都有 |
| `Disposition` / 回合状态机 | `service/turn/` | "合并、插话、排队"是本产品的对话策略 |
| `PlatformBrain` | `service/turns/` | 它做的是"把语音/主动消息接到本产品的 SubmitService" |
| `RoleProfile` | `agent/prompt/` | 提示词用的角色视图，不是角色的存储 |
| 角色卡解析（`card.py` / `catalog.py`） | `agent/roles/` | 纯解析，不碰文件系统；从哪读由 service 决定 |
| 产品工具（`recall_facts` 等） | `service/tools_impl/` | 用到了时间线、提醒这些产品概念 |
| 工具框架（注册表、授权、确认） | `agent/tools/` | 与产品无关 |
| 记忆 | `agent/memory/` | 记忆能力可复用；`memory/sql.py` 用的是共享的 `db/schema.py` |

## 已知遗留

1. **`memory_hub` 是第二个顶层包**（`src/memory_hub/`），只被 `companion` 自己用。按需求保留。
2. **`agent/memory/sql.py` 依赖 `db/schema.py`**：表定义在 `db`，实现的 SQL 在 `agent/memory`。
   如果以后要把 `agent` 抽成独立包，这条边要改成"表结构由使用方注册"。
3. **`prompt/plan.py` 的 `splice_injections` 触发 ruff UP047**（建议 PEP 695 泛型），基线就有。
