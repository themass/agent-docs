# ReMe 设计文档

[ReMe](https://github.com/agentscope-ai/ReMe)（Remember Me）源码整理，面向设计原理而非源码细节。
核验基准：本地 `/Users/gqli/work/deepagents/ReMe`，tag `v0.4.1.13-40-gd6b02a20`，整理日期 2026-10-21。

## 一句话

ReMe 把"记忆"做成了用户自己能读、能改、能迁移的 Markdown 文件，索引（BM25/向量/wikilink 图）只是可重建的派生数据，真相永远在磁盘上的 `.md` 文件里。

## 文档

| 文档 | 内容 |
|---|---|
| **[DESIGN.md](./DESIGN.md)** | 唯一的正文。Part I 核心理念（Memory as File）+ 运行时分层骨架；Part II 四层记忆模型 + **两个完整的对话/文件示例，逐步跟踪磁盘文件的产生与变化** + 检索与 proactive 流程；Part III 五个关键设计决策的 trade-off 分析 |

## 速查

### 四层记忆模型

| 层 | 目录 | 定位 | 可否重建 |
|---|---|---|---|
| 源记录 | `session/`、`resource/` | 原始对话 JSONL、用户上传文件，不可再生的一次性证据 | 不可（唯一真相源） |
| 轻处理 | `daily/` | 当天的工作台，一事一卡 + 当天索引页，回答"发生了什么" | 可从源记录重新蒸馏，但代价是重新调用 LLM |
| 深处理 | `digest/` | 跨天沉淀的长期抽象，回答"以后还能用上什么" | 可从 daily 重新 dream，但代价是重新调用 LLM |
| 系统索引 | `metadata/` | BM25、向量、wikilink 图、file_catalog | 完全可重建（`reme reindex`） |

### 五个核心自动化能力

| 能力 | 触发方式 | 读 | 写 |
|---|---|---|---|
| `auto_memory` | 显式调用（通常由宿主 Agent 在对话结束时触发） | `session/dialog/` | `daily/<date>/*.md` + `daily/<date>.md` |
| `auto_resource` | `resource_watch_loop`（background，监听 `resource/`） | `resource/**` | `daily/<date>/*.md` |
| `auto_index`（`index_update_loop`） | background，监听 `daily/` 与 `digest/` | 变化的 `.md` 文件 | `metadata/`（BM25、向量、wikilink 图） |
| `auto_dream` | `dream_cron`，每天 23:00 | 近 2 天 `daily/` 变化 | `digest/{procedure,personal,wiki}/*.md` |
| `proactive_read` | 读：显式调用；写：`proactive_refresh_cron` 每天 18:00 | 近 2 天 `daily/` 变化 | `daily/<date>/interests.yaml`（不写 digest） |

### 运行时八层骨架

```text
CLI → Service(HTTP/MCP) → Application → Job(base/stream/background/cron) → Step → Component → Schema → Config
```

四种 Job backend：`base`（一次请求跑完）、`stream`（边跑边吐流）、`background`（进程常驻，watch 文件系统，强制 `enable_serve=False`）、`cron`（定时触发）。记忆的"自动"二字主要靠 `background` 和 `cron` 这两种常驻/定时 Job 实现，不靠用户手动调用。

## 几个值得单独记住的设计思考

1. **File 是第一公民，Index 是派生物**。"ReMe memory is... first a file owned by the user and only then indexed by the system for retrieval."——这决定了迁移、备份、人工编辑都直接作用于文件，不需要特殊接口。
2. **daily 回答"发生了什么"，digest 回答"以后还能用上什么"**。两者不是一份数据的两个副本，而是有意保留的两种不同粒度——避免一次性的偶然细节被过早固化成长期记忆。
3. **Wikilink 坚持显式全路径**，牺牲手写便利性，换取可预测性、可移植性、可自动维护性（重命名时能批量重写入链）。
4. **检索默认关闭向量，只用 BM25 + wikilink 展开**。记忆内容本身是结构化 Markdown，关键词信噪比已经很高；语义相关性更多靠 Integrate 阶段显式写入的链接来补偿，而不是靠向量相似度去猜。
5. **Extract 和 Integrate 拆成两步**：Extract 决定"值得记吗"（全局、跨文件），Integrate 决定"怎么记、记到哪"（局部、逐 unit）。Integrate 没有 SKIP 动作——值得记的判断权完全交给 Extract。
6. **auto_link 不是独立 Job，而是 Integrate 阶段的能力**，因为建链需要的检索（`node_search`）和去重判断用的是同一次调用，拆开会出现"内容已落盘但链接未建好"的中间态。
7. **Proactive 和 Auto Dream 是两条不交叉的平行流水线**：前者产出有时效性、会过期的"今日关注清单"，后者产出持久的长期知识；两者的失败互不传染。
8. **明确的能力边界**：ReMe 只做跨会话的长期记忆，不做单会话的上下文窗口管理——"Single-session context-window management is outside the scope of ReMe v4... Those capabilities belong in the host agent framework."

## 阅读建议

直接读 [DESIGN.md](./DESIGN.md)。它是单篇文档，按 Part I → II → III 顺序读下来即可；Part II 的两个示例（第 4、5 节）是理解整套系统最快的路径——如果只有时间读一部分，优先读这两节。
