# Hermes Agent Telegram 看板多Agent协作指南

> **文档状态**: Deep / Historical · 正文可能含旧行号
> **Canonical 导航**: [ARCHITECTURE.md](ARCHITECTURE.md) · [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) · [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md)
> **版本核对**: 0.19.0 / 2026-07-22（本文件未全量重写）


> **Hermes 版本锚点**: 0.19.0 · **核对**: 2026-07-22 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)  
## 📋 概述

Hermes Agent 新版本引入了基于 **Telegram Topics（话题/看板）** 的多Agent协作能力，允许用户在单个Telegram Bot中通过创建不同的Topic来管理多个并行的Agent会话。每个Topic都是一个独立的Hermes会话通道，可以同时处理不同的任务。

---

## 🎯 核心概念

### 1. 什么是Telegram Topics？

Telegram Topics是Telegram Bot API 9.4+引入的功能，允许在私聊中创建类似"频道"或"看板"的话题分区。Hermes利用这一特性实现：

- **并行会话**：每个Topic对应一个独立的Hermes Agent会话
- **任务隔离**：不同Topic中的任务互不干扰
- **上下文分离**：每个Topic维护自己的对话历史和记忆

### 2. 系统架构

```
Telegram DM (Root/Main Chat)
├── System Lobby (系统大厅)
│   ├── /topic - 查看状态和未关联会话
│   ├── /status - 系统状态
│   ├── /sessions - 会话列表
│   └── /help - 帮助信息
│
├── Topic 1: "Research Project" → Session A
│   ├── 独立对话历史
│   ├── 独立记忆
│   └── 独立Agent状态
│
├── Topic 2: "Code Review" → Session B
│   ├── 独立对话历史
│   ├── 独立记忆
│   └── 独立Agent状态
│
└── Topic 3: "Data Analysis" → Session C
    ├── 独立对话历史
    ├── 独立记忆
    └── 独立Agent状态
```

---

## 🚀 快速开始

### 步骤1: 激活多会话模式

在Telegram中与Hermes Bot的根聊天（主DM）发送：

```text
/topic
```

Hermes会：
1. 检查Telegram Bot是否支持Topics功能
2. 验证`has_topics_enabled`和`allows_users_to_create_topics`
3. 为该用户启用多会话Topic模式
4. 发送引导消息并固定（如果配置允许）
5. 列出可以恢复到Topic中的旧会话

**引导消息示例**：
```
Multi-session mode is enabled.

Create new Hermes chats with the + button in this bot interface. 
Each Telegram topic is an independent Hermes session, so you can 
work on different tasks in parallel.

This main chat is reserved for system commands, status, and 
session management.

To restore an old session:
1. Use /topic here to see unlinked sessions.
2. Create a new topic with the + button.
3. Send /topic <session_id> inside that topic.
```

### 步骤2: 创建新的Topic会话

在Telegram Bot界面中：
1. 点击 **"+" 按钮**创建新Topic
2. 为Topic命名（如："Project Alpha"、"Bug Fixing"等）
3. 在新Topic中发送第一条消息

Hermes会自动：
- 检测到新的`message_thread_id`
- 创建一个新的Hermes会话
- 建立Topic到会话的绑定关系
- 在该Topic的会话上下文中运行Agent

### 步骤3: 并行工作

现在你可以：
- 在**Topic 1**中讨论项目A的设计
- 在**Topic 2**中调试代码问题
- 在**Topic 3**中分析数据

每个Topic都是完全独立的，互不影响！

---

## 📖 命令参考

### `/topic` - 在主聊天中

**用途**：查看多会话模式状态和未关联的旧会话

**输出示例**：
```
Telegram multi-session topics are enabled.

Create new Hermes chats with the + button in this bot interface.

Unlinked previous sessions:
1. 2026-05-01 Research notes — id: abc123
2. 2026-04-30 Deploy debugging — id: def456
3. Untitled session — id: ghi789

To restore one:
1. Create a new topic with the + button.
2. Open that topic.
3. Send /topic <id>
```

### `/topic` - 在Topic中（无参数）

**用途**：查看当前Topic绑定的会话信息

**输出示例**：
```
This topic is linked to:
Session: Research notes
ID: abc123

Use /new to replace this topic with a fresh session.
For parallel work, create another topic with the + button.
```

### `/topic <session_id>` - 在Topic中

**用途**：将旧的/未关联的会话恢复到当前Topic

**行为**：
1. 验证会话所有权（必须是同一用户的会话）
2. 检查会话是否已链接到其他Topic（MVP不允许重复链接）
3. 切换当前Topic到目标会话
4. 发送确认消息和最后一条Hermes回复

**输出示例**：
```
Session restored: Research notes

Last Hermes message:
[显示该会话的最后一条Assistant消息]
```

### `/new` - 在主聊天中（激活后）

**行为**：拒绝创建新会话，提示使用"+"按钮

**输出**：
```
To start a new parallel Hermes chat, create a new topic with 
the + button in this bot interface.

Each topic is an independent Hermes session. Use /new inside 
a topic only if you want to replace that topic's current session.
```

### `/new` - 在Topic中

**行为**：在当前Topic中创建新会话（替换现有会话）

**警告**：
```
Started a new Hermes session in this topic.

Tip: for parallel work, create a new topic with the + button 
instead of using /new here. /new replaces the session attached 
to the current topic.
```

### 普通文本消息 - 在主聊天中（激活后）

**行为**：拒绝进入Agent循环，提示使用Topic

**输出**：
```
This main chat is reserved for system commands.

To chat with Hermes, create a new topic using the + button 
in this bot interface. Each topic works as an independent 
Hermes session.
```

### 普通文本消息 - 在Topic中

**行为**：正常的Hermes Agent流程，在该Topic的会话上下文中运行

---

## 💾 数据存储

### SQLite表结构

Hermes使用两个专门的SQLite表来管理Telegram Topic模式：

#### 1. `telegram_dm_topic_mode` - Topic模式激活状态

存储每个用户/聊天的激活状态：

```sql
CREATE TABLE telegram_dm_topic_mode (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    activated_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    has_topics_enabled INTEGER,
    allows_users_to_create_topics INTEGER,
    capability_checked_at REAL,
    intro_message_id TEXT,
    pinned_message_id TEXT
);
```

**字段说明**：
- `chat_id`: Telegram聊天ID（主键）
- `user_id`: Telegram用户ID
- `enabled`: 是否启用（1=启用，0=禁用）
- `activated_at`: 激活时间戳
- `has_topics_enabled`: Bot是否启用了Topics功能
- `allows_users_to_create_topics`: 是否允许用户创建Topics
- `intro_message_id`: 引导消息ID
- `pinned_message_id`: 固定的引导消息ID

#### 2. `telegram_dm_topic_bindings` - Topic到会话的绑定

存储Telegram Topic与Hermes会话的映射关系：

```sql
CREATE TABLE telegram_dm_topic_bindings (
    chat_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_key TEXT NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    managed_mode TEXT NOT NULL DEFAULT 'auto',
    linked_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (chat_id, thread_id)
);

CREATE UNIQUE INDEX idx_telegram_dm_topic_bindings_session
ON telegram_dm_topic_bindings(session_id);

CREATE INDEX idx_telegram_dm_topic_bindings_user
ON telegram_dm_topic_bindings(user_id, chat_id);
```

**字段说明**：
- `chat_id`: Telegram聊天ID
- `thread_id`: Topic的线程ID（即`message_thread_id`）
- `user_id`: Telegram用户ID
- `session_key`: Hermes会话键
- `session_id`: Hermes会话ID（外键，级联删除）
- `managed_mode`: 管理模式
  - `auto`: 自动创建（用户首次发消息时）
  - `restored`: 恢复的旧会话
  - `new_replaced`: 通过`/new`替换的会话
- `linked_at`: 绑定时间戳
- `updated_at`: 更新时间戳

**约束**：
- 主键：`(chat_id, thread_id)` - 每个Topic只能有一个绑定
- 唯一索引：`session_id` - MVP中一个会话只能链接到一个Topic
- 索引：`(user_id, chat_id)` - 加速用户查询

### 迁移机制

Topic模式的表结构采用**显式迁移**策略：

1. **不会在启动时自动创建**：普通的`SessionDB()`初始化不会创建这些表
2. **首次`/topic`激活时创建**：调用`apply_telegram_topic_migration()`方法
3. **向后兼容**：如果未激活，旧的Telegram行为保持不变
4. **版本控制**：通过`state_meta.telegram_dm_topic_schema_version`跟踪

---

## 🔧 配置

在`config.yaml`中配置Telegram平台：

```yaml
platforms:
  telegram:
    extra:
      multisession_topics:
        enabled: false              # 全局开关（默认关闭）
        mode: user_managed_topics   # 用户自主管理Topics
        root_chat_behavior: system_lobby  # 根聊天作为系统大厅
        pin_intro_message: true     # 是否固定引导消息
```

**配置说明**：
- `enabled: false`：保持现有Telegram行为不变
- 通过`/topic`命令可以为单个聊天启用，前提是全局配置允许
- `root_chat_behavior: system_lobby`：激活后根聊天变为系统大厅

---

## 🎨 使用场景

### 场景1: 多项目并行开发

```
Topic 1: "Frontend Redesign"
  - 讨论UI/UX设计
  - 生成React组件代码
  - 审查前端架构

Topic 2: "Backend API"
  - 设计RESTful API
  - 编写FastAPI端点
  - 数据库schema设计

Topic 3: "DevOps Pipeline"
  - 配置CI/CD流程
  - Docker容器化
  - Kubernetes部署策略
```

### 场景2: 学习与研究

```
Topic 1: "Python Learning"
  - Python基础教程
  - 练习题解答
  - 最佳实践讨论

Topic 2: "Machine Learning"
  - ML算法研究
  - 模型训练实验
  - 论文阅读笔记

Topic 3: "System Design"
  - 架构模式学习
  - 案例分析
  - 设计决策讨论
```

### 场景3: 团队协作模拟

虽然目前只支持单用户，但可以用Topics模拟团队角色：

```
Topic 1: "Product Manager"
  - 需求分析
  - 产品规划
  - 优先级排序

Topic 2: "Tech Lead"
  - 技术选型
  - 架构评审
  - Code Review

Topic 3: "QA Engineer"
  - 测试用例设计
  - Bug报告分析
  - 质量保障策略
```

### 场景4: 长期项目管理

```
Topic 1: "Project Alpha - Sprint 1"
  - 当前迭代任务
  - 每日站会记录
  
Topic 2: "Project Alpha - Sprint 2"
  - 下一迭代计划
  - 待办事项

Topic 3: "Project Alpha - Retrospective"
  - 回顾会议记录
  - 改进建议
```

---

## ⚙️ 高级功能

### 恢复旧会话

如果你有之前创建的Telegram会话（在启用Topic模式之前），可以将它们恢复到新的Topic中：

1. 在主聊天中运行`/topic`查看未关联的会话列表
2. 用"+"按钮创建一个新Topic
3. 在新Topic中发送`/topic <session_id>`
4. Hermess会将该会话恢复到这个Topic

**限制**：
- 只能恢复属于同一用户的会话
- MVP中一个会话不能同时链接到多个Topic
- 恢复后会发送确认消息和最后一条Hermes回复

### 会话管理模式

`managed_mode`字段标识Topic是如何与会话关联的：

- **`auto`**：用户首次在新Topic中发消息时自动创建
- **`restored`**：通过`/topic <session_id>`恢复的旧会话
- **`new_replaced`**：在Topic中使用`/new`替换的会话

这有助于追踪会话的来源和管理历史。

### 系统大厅命令

激活Topic模式后，主聊天变为系统大厅，支持的命令包括：

- `/topic` - 查看状态和未关联会话
- `/status` - 系统状态
- `/sessions` - 会话列表（如果可用）
- `/usage` - 使用情况统计
- `/help` - 帮助信息
- `/platforms` - 平台信息
- `/models` - 模型信息
- `/memory` - 记忆管理

---

## ⚠️ 注意事项

### 1. 不要滥用`/new`

在Topic中使用`/new`会**替换**当前Topic的会话，而不是创建并行会话。如果需要并行工作，应该：
- ✅ 使用"+"按钮创建新Topic
- ❌ 避免在同一个Topic中频繁使用`/new`

### 2. 会话唯一性

MVP中，一个Hermes会话只能链接到一个Telegram Topic。如果你尝试将已链接的会话恢复到另一个Topic，会被拒绝。

### 3. 主题命名

虽然Hermes不强制要求特定的Topic命名规范，但建议使用清晰的名称：
- ✅ "Project Alpha - Backend"
- ✅ "Learning - Python Basics"
- ❌ "Test 1", "asdf", ""

### 4. 数据持久化

- Topic绑定信息存储在SQLite数据库中
- 即使重启Hermes Gateway，绑定关系也会保留
- 删除会话时，相关的Topic绑定会通过外键级联删除

### 5. 性能考虑

- 每个Topic都是独立的会话，有自己的上下文和记忆
- 大量并行的Topic会增加内存使用
- 建议根据实际需求合理控制Topic数量

---

## 🔍 故障排查

### 问题1: `/topic`命令返回错误

**可能原因**：
- Telegram Bot未启用Topics功能
- Bot API版本过低（需要9.4+）

**解决方案**：
1. 在BotFather中检查Bot设置
2. 确保启用了"Topics"或"Forum"功能
3. 更新python-telegram-bot库到最新版本

### 问题2: 创建Topic后没有响应

**可能原因**：
- `message_thread_id`未被正确识别
- 会话绑定失败

**解决方案**：
1. 检查Gateway日志中的错误信息
2. 确认Telegram消息包含`message_thread_id`字段
3. 验证数据库迁移是否成功执行

### 问题3: 无法恢复旧会话

**可能原因**：
- 会话不属于当前用户
- 会话已链接到其他Topic

**解决方案**：
1. 使用`/topic`查看会话的所有权信息
2. 检查会话是否已在其他Topic中活跃
3. 如需移动会话，先在原Topic中使用`/new`释放它

### 问题4: Topic中的消息发送到错误的会话

**可能原因**：
- 绑定关系混乱
- `message_thread_id`映射错误

**解决方案**：
1. 在Topic中运行`/topic`检查当前绑定
2. 如有必要，使用`/new`重置Topic的会话
3. 检查数据库中的`telegram_dm_topic_bindings`表

---

## 📊 监控与管理

### 查看所有Topic绑定

可以通过直接查询SQLite数据库来查看所有Topic绑定：

```bash
sqlite3 state.db "SELECT * FROM telegram_dm_topic_bindings;"
```

### 查看Topic模式状态

```bash
sqlite3 state.db "SELECT * FROM telegram_dm_topic_mode;"
```

### 清理未使用的绑定

如果某些Topic已被删除但绑定仍存在，可以手动清理：

```bash
# 谨慎操作！先备份数据库
sqlite3 state.db "DELETE FROM telegram_dm_topic_bindings WHERE chat_id = 'YOUR_CHAT_ID' AND thread_id = 'DELETED_THREAD_ID';"
```

---

## 🔄 未来规划

### 计划中的功能

1. **Live Status Suffixes**：在Topic标题中显示实时状态（如"🟢 Active"、"⏸️ Paused"）
2. **Topic Title Sync**：自动同步Topic标题与会话名称
3. **跨Topic搜索**：在所有Topic中搜索对话内容
4. **Topic模板**：预定义的Topic配置模板
5. **批量管理**：批量创建、删除、归档Topic
6. **权限管理**：在多用户场景中支持Topic级别的权限控制

### 可能的改进

1. **智能Topic建议**：根据对话内容自动建议Topic分类
2. **Topic合并**：将相关的Topic合并为一个
3. **会话迁移**：在不同Platform之间迁移Topic会话
4. **Topic统计**：每个Topic的活动统计和分析

---

## 📚 相关文档

- [Hermes Agent 架构文档](./ARCHITECTURE.md)
- [会话管理系统](./MEMORY_SYSTEM.md)
- [Telegram平台集成](../gateway/platforms/telegram.py)
- [SessionDB实现](../hermes_state.py)

---

## 💡 最佳实践

### 1. 组织你的Topics

```
推荐结构：
- 按项目分：Project-A, Project-B, Project-C
- 按类型分：Coding, Writing, Research, Planning
- 按时间分：Sprint-1, Sprint-2, Sprint-3
- 按角色分：PM-Perspective, Dev-Perspective, QA-Perspective
```

### 2. 定期清理

- 完成的项目Topic可以归档或删除
- 使用`/new`重置不再需要的Topic
- 定期运行`/topic`检查未关联的会话

### 3. 命名规范

```
好的命名：
✅ "E-commerce Platform - Backend API"
✅ "ML Experiment - Image Classification v2"
✅ "Blog Post - AI Trends 2026"

不好的命名：
❌ "Test"
❌ "New Chat"
❌ "123"
```

### 4. 会话隔离

- 不要在同一个Topic中混合完全不同的任务
- 为每个主要任务创建专用的Topic
- 使用清晰的Topic名称便于后续查找

---

## 🎉 总结

Hermes Agent的Telegram看板多Agent协作功能为你提供了：

✅ **并行工作能力** - 同时处理多个任务  
✅ **上下文隔离** - 每个Topic独立维护对话历史  
✅ **灵活管理** - 轻松创建、恢复、切换会话  
✅ **清晰组织** - 通过Topic名称分类管理任务  
✅ **向后兼容** - 不影响现有的Telegram使用方式  

开始使用很简单：
1. 发送`/topic`激活功能
2. 点击"+"创建新Topic
3. 开始并行工作！

享受高效的多任务Agent协作体验！🚀
