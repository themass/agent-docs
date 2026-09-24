# Session 会话完整生命周期‑数据变化实例

## 场景设定

开启一个长期会话，分多轮交互、后台异步任务、上下文自动压缩、多次快照读写。

跟踪三样核心数据：

1. `messages`：对话消息列表
2. `tool_metadata["async_agent_tasks"]`：后台任务镜像清单
3. 磁盘快照持久化文件

**AutoCompactState 上下文压缩触发规则**：消息数量到达阈值，自动将早期历史压缩成摘要，减少 token 消耗。

## 会话时间线总览

表格

| 阶段 | 事件 | SessionBackend 动作 |
| --- | --- | --- |
| 阶段 0 | 会话打开，加载历史快照 | `load_snapshot()` 读磁盘 → 加载至内存 |
| 阶段 1 | 普通对话交互 2 轮 | 每轮结束 `save_snapshot()` |
| 阶段 2 | Coordinator 发起 2 个后台 Worker 任务 | 任务加入 `async_agent_tasks`，快照保存 |
| 阶段 3 | Worker‑A 完成 → drain 推送通知，开启 follow‑up 回合 | 标记 `notification_sent=True`，快照保存 |
| 阶段 4 | 消息超长，触发上下文自动压缩 AutoCompact | `messages` 被压缩，快照保存 |
| 阶段 5 | Worker‑B 完成 → drain 推送通知 | 标记 `notification_sent=True`，快照保存 |
| 阶段 6 | 关闭会话 / 后续重新打开会话 | 再次 `load_snapshot` 加载最新状态 |

---

## 逐阶段内存 & 磁盘数据快照变化演示

### 阶段 0：初始化加载会话（读磁盘）

**磁盘快照（持久化）**

```
{
  "messages": [
    {"role":"user","content":"你好"}
  ],
  "tool_metadata": {
    "async_agent_tasks": []
  }
}
```

执行：`bundle.session_backend.load_snapshot()`

>
> 👉 内存 QueryEngine 状态和磁盘完全一致
>
>
> - 内存 `messages` = `[user: 你好]`
> - `async_agent_tasks` = `[]`

---

### 阶段 1：第一轮普通交互，用户提新需求

>
> 用户：帮我统计两个文件
> LLM 回复：好的，马上处理

**内存变更，messages 追加两条消息**

```
{
  "messages": [
    {"role":"user","content":"你好"},
    {"role":"user","content":"帮我统计两个文件"},
    {"role":"assistant","content":"好的，马上处理"}
  ],
  "tool_metadata": {
    "async_agent_tasks": []
  }
}
```

回合结束触发 `save_snapshot()`

>
> 👉 磁盘 = 内存，完全同步

---

### 阶段 2：Coordinator 执行 agent 工具，启动 2 个后台任务

Assistant 返回 tool_call，启动 Worker‑A、Worker‑B。

>
> TaskManager（真相源）创建 2 个真实后台子进程；任务镜像写入内存。

**内存状态**

```
{
  "messages": [
    {"role":"user","content":"你好"},
    {"role":"user","content":"帮我统计两个文件"},
    {"role":"assistant","content":"好的，马上处理"},
    {"role":"assistant","tool_calls": ["启动Worker‑A","启动Worker‑B"]}
  ],
  "tool_metadata": {
    "async_agent_tasks": [
      {
        "task_id":"A",
        "notification_sent": false,
        "agent_id":"Worker‑A"
      },
      {
        "task_id":"B",
        "notification_sent": false,
        "agent_id":"Worker‑B"
      }
    ]
  }
}
```

回合结束交还控制权，进入 drain；回合结束触发 `save_snapshot()`

>
> 👉 磁盘保存两份待通知任务。
> ⚠️注意：磁盘快照**不会保存 Worker 进程本身**，只存储镜像清单。

---

### 阶段 3：Worker‑A 执行完毕，drain 发送通知消息

drain 轮询 TaskManager 发现 Worker‑A 状态 = `completed`

1. 内存修改镜像标记：`task_id:A → notification_sent = true`
>
> ⚠️此时仅仅修改内存！磁盘数据还未变更！
2. `submit_follow_up` 往 `messages` 追加一条虚拟用户通知消息：`[后台任务A已完成，结果:文件1统计完成]`
3. CoordinatorAgent 执行一轮新回合
4. follow‑up 回合结束 → `save_snapshot ()`

**内存状态**

```
{
  "messages": [
    {"role":"user","content":"你好"},
    {"role":"user","content":"帮我统计两个文件"},
    {"role":"assistant","content":"好的，马上处理"},
    {"role":"assistant","tool_calls": ["启动Worker‑A","启动Worker‑B"]},
    {"role":"user","content":"[后台任务A已完成，结果:文件1统计完成]"},
    {"role":"assistant","content":"收到任务A结果，等待任务B"}
  ],
  "tool_metadata": {
    "async_agent_tasks": [
      {
        "task_id":"A",
        "notification_sent": true
      },
      {
        "task_id":"B",
        "notification_sent": false
      }
    ]
  }
}
```

>
> 👉 `save_snapshot` 刷盘，磁盘同步 A 已通知标记。

---

### 阶段 4：消息列表过长 → AutoCompactState 触发上下文压缩

消息条数超过阈值，引擎启动上下文压缩：
将最早期的多条历史消息合并为一条摘要，释放 token 窗口空间。

**‑压缩前‑内存 messages（长列表）**
包含上面全部 6 条消息

**‑压缩后‑内存 messages（内存变更）**

```
{
  "messages": [
    {"role":"system","content":"【历史摘要】用户问好，请求统计两个文件；启动后台任务A、B，任务A已经完成，助手正在等待任务B结果。"},
    {"role":"user","content":"[后台任务A已完成，结果:文件1统计完成]"},
    {"role":"assistant","content":"收到任务A结果，等待任务B"}
  ],
  "tool_metadata": {
    "async_agent_tasks": [
      {
        "task_id":"A",
        "notification_sent": true
      },
      {
        "task_id":"B",
        "notification_sent": false
      }
    ]
  }
}
```

✅ 关键点：

>
> `async_agent_tasks` 后台任务镜像**完全不受压缩影响**！
> 压缩只会修改 `messages`，`tool_metadata` 原样保留。

压缩属于一轮回合变更，触发 `save_snapshot()`，磁盘写入压缩后的会话。

---

### 阶段 5：Worker‑B 执行完成，drain 交付第二条通知

1. drain 轮询 TaskManager 发现 Worker‑B 完成
2. 内存修改镜像 `task_id:B → notification_sent = true`
3. `messages` 追加任务 B 通知消息，Coordinator 执行 follow‑up 回合
4. 回合结束，`save_snapshot()`

**内存最终状态**

```
{
  "messages": [
    {"role":"system","content":"【历史摘要】用户问好，请求统计两个文件；启动后台任务A、B，任务A已经完成，助手正在等待任务B结果。"},
    {"role":"user","content":"[后台任务A已完成，结果:文件1统计完成]"},
    {"role":"assistant","content":"收到任务A结果，等待任务B"},
    {"role":"user","content":"[后台任务B已完成，结果:文件2统计完成]"},
    {"role":"assistant","content":"两个文件全部统计完毕"}
  ],
  "tool_metadata": {
    "async_agent_tasks": [
      {"task_id":"A","notification_sent": true},
      {"task_id":"B","notification_sent": true}
    ]
  }
}
```

>
> 👉 `save_snapshot` 落地磁盘。两个任务通知标记全部永久保存。

---

### 阶段 6：关闭会话后，隔一段时间重新打开该 session

执行 `load_snapshot()`读取最新磁盘快照，内存恢复上面这份数据。

⚠️ 重要风险：
此时 TaskManager 是全新空注册表。旧的 Worker‑A/B 进程早就消失了。
drain 读取内存 `async_agent_tasks`，两个任务标记都是`true`，知道通知已经发过，**不会重复发送通知**。

---

# 核心规律总结

1. 上下文压缩 (AutoCompact) **只会修改 messages**，绝对不动 `tool_metadata["async_agent_tasks"]`
2. 后台任务镜像清单独立于对话历史，不受摘要压缩影响。
3. 每次 follow‑up 回合完成之后才刷盘；**内存标记和磁盘快照之间存在短暂时间窗口不一致风险（崩溃重复通知）**
4. Worker 真实进程状态永远不在快照中，快照只是镜像副本。

# tool_metadata 是否持久化？

## 结论

`tool_metadata` 会完整存入会话快照（`SessionBackend.save_snapshot`）；它和 `messages` 是两大顶级持久化字段。

### 1. 源码证据（drain 里面 submit_follow‑up）

```
# submit_follow_up 末尾
await bundle.engine.submit_message(notification_payload)
# Coordinator回合跑完之后
bundle.session_backend.save_snapshot(engine, ...)
```

`save_snapshot` 序列化整个 QueryEngine 对象，落地磁盘的数据完整结构：

```
{
  "messages": [...对话消息列表...],
  "tool_metadata": {
    "async_agent_tasks": [
      {
        "task_id":"A",
        "notification_sent": true
      },
      {
        "task_id":"B",
        "notification_sent": false
      }
    ],
    "其它自定义key": "xxx"
  },
  "auto_compact_state": {...上下文压缩状态机数据...},
  "settings": {...会话配置...}
}
```

`async_agent_tasks` 仅仅是 `tool_metadata` 里面的其中一个子字段。

### 2. 上下文压缩会不会把 tool_metadata 删掉？

**不会**。
`AutoCompactState`（上下文自动压缩）只处理 `messages` 数组：把早期多条对话消息合并成一条 system 摘要消息；
`tool_metadata` 完全独立存储，不在消息列表里面，**永远不会被压缩、截断、合并、删除**。

隔离设计对照表

表格

| 字段 | 是否被上下文压缩修改 | 是否持久化快照 |
| --- | --- | --- |
| `messages` | ✅会（历史被压缩摘要） | ✅保存 |
| `tool_metadata` | ❌完全不受压缩影响 | ✅完整保存 |
| `async_agent_tasks`（tool_metadata 子项） | ❌不受压缩影响 | ✅完整保存 |
| BackgroundTaskManager 内存里面真实 worker 进程状态 | — | ❌不保存 |

### 核心区分

- `tool_metadata.async_agent_tasks`：镜像清单，持久化，存磁盘
- BackgroundTaskManager 内部实时任务状态：真相源，内存‑only，进程销毁即丢失

### 3. 重启会话时的读取行为

当你重新打开旧会话，`load_snapshot()` 会：

1. 把磁盘上完整的 `tool_metadata` 读回到内存 `engine.tool_metadata`；
2. drain 拿到这份恢复出来的 `async_agent_tasks` 清单，检查每一条 `notification_sent` 布尔标记；
3. 如果标记 = `true`，就知道后台任务通知已经发送过，不会重复推送消息。

### 4. 边界坑点：崩溃导致任务通知重复发送

>
> Worker‑A 完成 → 内存设置 `notification_sent=true`，**还未执行 save_snapshot，程序崩溃**

1. 内存中 `tool_metadata` 的改动全部丢失；
2. 磁盘快照里面 `notification_sent` 依旧 = `false`；
3. 重启后加载快照 → drain 会**重复发送一次任务 A 完成通知**。

根因：`tool_metadata` 的变更**只有执行 `save_snapshot` 之后，才真正写入磁盘**。