# claude-mem 设计文档

[claude-mem](https://github.com/thedotmack/claude-mem) 源码级整理，面向读写主流程、分层原理与架构设计。
核验基准：本地 `/Users/gqli/work/deepagents/claude-mem`，tag `v15.0.1-2-gbbb337902`，整理日期 2026-10-21。

## 一句话

claude-mem 是挂在 Claude Code 生命周期 hook 上的异步压缩管线：hook 进程把原始观察数据落盘排队，一个常驻 worker 异步调用 Claude Agent SDK 子进程把它压缩成结构化记录存进 SQLite；SQLite 是唯一权威源，Chroma 向量库只是可以随时整体重建的派生索引。核心哲学是**hook 永不阻塞、永不失败**。

## 文档

| 文档 | 内容 |
|---|---|
| **[DESIGN.md](./DESIGN.md)** | 唯一正文。Part I 进程拓扑（hook/worker/SDK子进程三种角色）；Part II 写入主流程（六个hook职责 + PostToolUse→spool→异步压缩的完整时序图）；Part III 存储分层（SQLite真相源 + Chroma派生索引 + dedup + reinforcement）；Part IV 检索流程（search/timeline/get_observations三层渐进式披露，Chroma主备切换而非RRF融合）；Part V **完整的调试会话示例**，逐步跟踪数据从 hook 事件到数据库行到下次会话注入的全过程；Part VI 六个关键设计思考 |

## 速查

### 三种进程角色

| 角色 | 生命周期 | 启动方 | 职责 |
|---|---|---|---|
| Hook 进程 | 毫秒级，一次性 | Claude Code 在每个生命周期节点触发 | 落盘排队，立刻退出，不等待结果 |
| Worker（常驻） | 长期存活 | 第一个需要它的 hook 懒启动 | 异步 drain 队列、调用 SDK 压缩、读写 SQLite/Chroma、服务 MCP 检索 |
| SDK 子进程 | 跟一次压缩绑定 | Worker 按需 spawn | 真正执行 `claude-agent-sdk` 的 `query()`，底层 spawn 独立 `claude` CLI 进程 |

注意：`src/server/` 不是本地 Worker Service，是另一条面向云端多租户部署的独立运行时（Postgres+BullMQ），与本地单机路径互斥，默认不会被用到。

### 写入链路（六个 hook）

| Hook 事件 | 作用 |
|---|---|
| SessionStart | 从 worker 拉取历史记忆，注入 `additionalContext` |
| UserPromptSubmit | 创建/延续 session，记录用户原始 prompt |
| PreToolUse | 文件/检索前置上下文增强（不产生记忆） |
| PostToolUse | **观察管线起点**：工具调用落盘排队 → 异步压缩成 observation |
| Stop | 取最后一条 assistant 消息生成会话级总结（独立的 `session_summaries` 表） |
| SessionEnd | 收尾事件 |

### 存储与检索分层

| 层 | 角色 |
|---|---|
| SQLite `observations` 表 | 唯一权威源，字段对应压缩后的 XML（title/subtitle/facts/narrative/concepts） |
| SQLite `session_summaries` 表 | 独立的会话级总结，不是 observation 的汇总视图 |
| Chroma 向量库 | 完全派生、可随时整体删除重建的语义索引，`metadata.sqlite_id` 回指权威行 |
| dedup | 基于标题 IDF 余弦的两档规则（exact 静默合并 / candidate 仅标记待审），非语义向量去重 |
| reinforcement | ACT-R 幂律衰减强度模型，基于日期序列，非 embedding |

检索三层：`search`（紧凑索引，~50-100 token/条）→ `timeline`（跨 session 的纯时间窗口）→ `get_observations`（按 ID 批量拉完整字段，~500-1000 token/条）。

## 几个值得单独记住的设计思考

1. **Hook 永不阻塞**：所有 hook 的异常路径都收敛到 exit 0，worker 挂掉不会让 Claude Code 感知到失败，只在连续失败达阈值后一次性提醒用户。压缩可以晚几秒，交互不能卡。
2. **排队用文件系统 + fs.watch，不是内存队列或消息中间件**：文件名本身就是去重键（会话哈希 + tool_use_id），天然支持 worker 重启后不丢事件、不重复消费。
3. **模型输出空间被收紧到严格 XML 骨架 + 一个显式哨兵值**（`<skip_summary reason="noise" />`），不允许用自然语言表达"跳过"，让解析层可以做确定性校验。
4. **去重和强化都刻意选择"更笨但更可控"的方法**：候选去重用 IDF 余弦而非向量相似度（真实数据验证过 simhash 方案假阳性泛滥），强化用日期序列幂律衰减而非 embedding 置信度——都是因为这两处的错误代价是不可逆的数据丢失或排序错乱。
5. **Chroma 宁可整体重建，不维护脆弱的最终一致性**：索引损坏时直接删除整个 collection 从 SQLite 重建，不做增量修复。
6. **检索的"混合"是带着领域知识的主备切换，不是通用 RRF 融合**：Chroma 优先，只对"真的返回空"的类别用 SQLite 补洞，因为 Chroma 的跨类型 top-N 查询有"类别互相挤占召回名额"的已知失败模式（CJK 查询下 prompts 挤占 observations 是文档里举的具体例子）。

### 与 ReMe 的对照

两个记忆系统做出了相反的存储选择：ReMe 把文件当作第一公民，索引是派生物，用户能直接读写 Markdown；claude-mem 把 SQLite 行当作第一公民，文件（Chroma 向量）反而是派生物，但数据库字段本身模仿了结构化笔记的骨架（标题/事实/叙述/概念）。两者都认同"压缩后的记忆应该是结构化、可解析的"，只是在"要不要让人类直接触碰存储介质"这件事上给出了不同答案。详见 [ReMe-architecture/DESIGN.md](../ReMe-architecture/DESIGN.md) Part III 的检索设计对比。

## 阅读建议

直接读 [DESIGN.md](./DESIGN.md)，按 Part I → VI 顺序。如果只有时间读一部分，优先读 Part II 的时序图和 Part V 的完整示例——这两节是理解整条数据流最快的路径。
