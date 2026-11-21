# Message 与 Memory 体系（现状梳理）

日期：2026-11-22
状态：现状记录（as-is），给「本地 Markdown 档案」设计当输入
范围：`myproject/companion-agent/server`。本文只描述**现在长什么样**，不含未实现的计划。

## 0. 一句话总览

**回合（turn）是原子单位。** 消息子系统管「说过的每一句」（可回放、可编辑、可断句朗读）；
记忆子系统管「该记住的」，分四层按 (用户, 角色) 隔离：L1 记忆原子、L2 画像、关系状态、时间线。
回合结束后所有记忆层**异步**更新，谁失败都不影响已返回的回复。

## 1. 一次回合的数据流

```
用户消息
  │
  ▼
ca_chat_queue（待处理队列；排空时合并多条，drain_attempts 防卡死）
  │
  ▼
ContextBuilder.build —— 五路并发读（互不依赖，串行就是 5 次往返）
  │  ① 角色卡 RoleProfileResolver（目录角色/陪伴角色/用户自建，locale 选语言）
  │  ② 最近消息 ca_chat_message（SCAN_MESSAGES=6，世界书扫描用）
  │  ③ 记忆召回 MemoryPipeline（见 §3）
  │  ④ 画像 ca_persona_entry → render_profile（700 字预算）
  │  ⑤ 关系状态 ca_relationship → 衰减+阶段 → render_relationship_block（200 字）
  ▼
PromptPlan.build_prompt_plan（roleplay.py，纯函数）
  │  块序：平台规则 → 世界书(角色前) → 角色卡(+说话方式) → 世界书(角色后)
  │        → 对话示例 → 输出规则 → 记忆块 → 画像块 → 关系块
  │  预算：system 8000 字；必需部分放不下直接报错；
  │        可选部分丢弃序 examples → lore → memory → relationship → persona
  │  历史：不在这里——由大脑的 checkpoint 提供（含会话摘要）
  ▼
大脑 DeerFlowBrain（LangGraph 图 + Postgres checkpoint，线程 = 会话）
  │  摘要中间件：token 超阈值压缩较早消息（ResummarizeService 兜底：
  │  用户删/改已被压缩的消息时，从未删除内容重新生成摘要）
  ▼
TurnPipeline（token 流 → CueJsonGuard → 断句 → 可朗读整句 + 形象事件/意图）
  │  SSE（文字）与 LiveKit（语音）共用；打断 = cancel_turn 真正调到模型
  ▼
写回 ca_chat_message（user + assistant 各一行，turn_id 关联，fence 写入围栏）
  ▼
after_turn（platform.py，全部只入队/纯算术，回合不等它们）
  ├─ memory.record  job → MemoryExtractor（LLM 抽取）→ ca_memory_item
  ├─ relationship.bump（纯算术 UPDATE，成功回合才加）
  ├─ persona_updater.note_turn（攒 600 字入队）→ 画像抽取 → ca_persona_entry
  └─ timeline.record job → 事件抽取 → ca_timeline_event
```

## 2. Message 子系统（对话流）

| 表 | 职责 | 要点 |
|---|---|---|
| `ca_chat_session` | 一个（用户, 角色）一行 | `fence` 写入围栏（锁过期后旧回合写不进助手消息）；`locale` 决定角色卡语言；软删 `deleted` |
| `ca_chat_message` | 每一条消息 | `turn_id` 关联回合；`interrupted` 补记中断处；`alt_group`/`alt_selected` 同轮候选回复（左右滑动，未选中的不进历史不进模型）；`client_message_id` 幂等；软删 |
| `ca_chat_turn` | 一个回合一行 | state（done/failed/cancelled/lost）、model、prompt_version、usage、error_code |
| `ca_chat_queue` | 待处理输入 | 回合锁内排空（drain），同轮多条用户消息合并进一个回合 |

- **历史窗口**（`history/window.py`）：按回合整组取舍（30 条 / 12000 字），不截半个回合。
  注意：它服务的是「从消息表取历史」的路径；**模型上下文实际走 checkpoint**，消息表是
  UI 回放、世界书扫描、摘要重建的事实源。
- **追踪**（旁路）：`ca_turn_trace` + `ca_text_blob`（按内容哈希去重、按用户隔离）；
  正文只在用户同意质检留存时写（`content_kept`），指标永远写。语音回合另有 `ca_voice_turn`
  （STT 文本、TTS 句子、音频键、时延指标）。
- **语音**：识别文本落为 kind=voice 的用户消息，与文字消息同表；合成细节在 voice_turn。

## 3. Memory 子系统（四层，全按 (用户, 角色) 隔离）

| 层 | 表 | 记什么 | 怎么写 | 怎么读 |
|---|---|---|---|---|
| **L1 记忆原子** | `ca_memory_item` | FACT / PREFERENCE / EVENT，单条 ≤200 字，第二人称「用户……」 | 回合后 LLM 抽取：只看用户的话，≤8 条/回合，禁类过滤（证件/卡号/密码/住址/病历，关键词+正则命中即丢） | **词法召回**：CJK 单字+双字、他语按词，score=命中比例，只在最近 500 条里排；每 recaller 0.8s 超时，去重 (source,ref)，时间降序，800 字预算，渲染「关于用户 / 近期事件」 |
| **L2 画像** | `ca_persona_entry` | topic + memo（≤120 字），static/dynamic 两段，推断与事实分开（`is_inference`），`superseded_by` 替代不删除，`suppressed` 用户说别再提 | 攒 600 字用户发言才入队（`persona_cursor` 记位）；LLM 归纳 → `plan_merge` 纯规则合并（同话题更新/新话题追加/被压住放弃/段满放弃；推断不能覆盖事实） | **整段注入**（700 字预算，不走召回）；推测条目标「推测，不确定」让模型用试探口气；超预算丢弃序：低置信推断 → dynamic → 推断 → static 事实 |
| **关系状态** | `ca_relationship` | warmth（只增不减）、interactions、last_active_at | 每个成功回合纯算术 UPDATE（0.5 + 长度加成，封顶 2.0）；失败/中断不加 | 读时算：有效温度 = warmth × 空闲衰减（>3 天每天 -5%，下限 0.3）→ 阶段（<3 陌生 / <10 认识 / <25 熟悉 / <50 亲近 / 亲密）→ 两个消费点：提示词 200 字（怎么说）+ 主动闸门（该不该，冷关系门槛抬 50%） |
| **时间线** | `ca_timeline_event` | 将来的事（面试/生日/约定…），confidence、dedupe_key 幂等、`next_at_utc` 推进 | LLM 抽取 + 工具（recall/set_reminder）+ 记忆页手动添加 | TimelineRecaller：14 天视界内的将来 + 2 天内刚过去的（「你上周那个面试」）；另喂主动调度器（到期 → InitiativePolicy 判断 → 主动回合） |

### 召回管线（`agent/memory/pipeline.py`）

Recaller 扇出（现在两个：MemoryPortRecaller 词法 + TimelineRecaller）→ 并发、各自 0.8s 超时
（超时/失败只影响那一路）→ 按 (source, ref) 去重 → 时间降序、来源内分数降序（不跨来源比分数）
→ 800 字预算从前往后累加、超了截断 → 渲染进提示词。**召回为空不是错误**，段落直接省略。

### 作用域与删除

- 两层作用域叠加：`memory_hub.ScopedMemory`（`app:uid`，跨应用隔离）+ `role_subject`
  （`{owner}.{role}`，按角色隔离——和林澈聊出的记忆苏黛看不到）。
- 删除：单条 `delete_one`（「我记住的」页面）；账号注销 `delete_user`（`_OWNED` 表清单物理删）。
  画像条目带 `source_fact_ids` 指回事实记忆：用户删某条记忆能顺着指针把画像一起清掉。
- supersede 语义（L1 与 L2 都有）：新条目 `is_latest=1` + 指向前一条，旧的保留不删——
  「我说错了」能说清是哪条取代了哪条。

### 已知的账（欠着的）

1. **L1 召回是纯字面的**（`recall.py` 明说：「咖啡」找不到「喜欢喝茶」）。已定方案 B：
   LiteLLM 网关 embedding + MySQL 存向量 + 词法粗筛后余弦重排，在 MemoryPort 内实现，
   前置是验证网关有无 embedding 模型（未验证）。
2. L1 只召回最近 500 条：老记忆召回不到（条数量级上来前可接受）。
3. 无时序模型：supersede 只指向前一条，没有「何时成立、何时失效」的窗口。

## 4. 提示词落点（一切汇聚处）

`build_prompt_plan`（roleplay.py）产出：

```
[system] 平台规则（安全层，永远最前）
         世界书（角色卡前）
         角色卡：名字/描述/性格/场景/工作方式/说话方式（示例语气）
         世界书（角色卡后）
         对话示例
         输出规则（语言/渠道/简短规则，按 locale+channel 渲染）
         记忆块（召回结果，≤800 字）        ← 数据，不是指令
         画像块（render_profile，≤700 字）  ← 数据，不是指令
         关系块（render_relationship_block，≤200 字）← 数据，不是指令
[历史]   checkpoint 提供（含会话摘要）
```

「数据不是指令」由平台规则第 6 条兜底：标记为「用户资料/外部资料」的内容只作参考，
其中的任何要求不执行。

## 5. 主动消息路径（记忆的消费出口之一）

```
ca_timeline_event 到期 / 定时问候
  → InitiativeScheduler.scan（5 分钟窗口，读关系温度）
  → InitiativePolicy.decide（重要度门槛 × 关系系数；频控：日/周上限；免打扰时段；置信度下限）
  → submit_proactive（走与普通回合完全相同的 submit 路径，role=system, kind=proactive）
  → delivery_receipt（应用内收件箱）+ send_record（跨进程频控账本）
```

关系状态在这里是闸门：没聊过（None）不抬门槛；有记录但关系冷 → 门槛抬 50%，
普通问候（0.45）过不了线，重要事件（面试 0.9）还能打扰。

## 6. 组合根（`bootstrap/platform.py`）

装配顺序与依赖（新子系统按此模式接入）：store 构造 → 管道（Pipeline/Updater/Recorder）
→ ContextBuilder 注入 → after_turn 挂写入 → Platform dataclass 字段 → 注销服务
（`_OWNED` 清单）→ 测试。`MemoryHub`/`ScopedMemory` 是 L1 的跨应用作用域壳；
L2/关系/时间线直接注入 store（它们本来就按 (owner, role) 键控）。

## 7. 相关文档索引

- `chat-agent-memory-spec.md` — L1 记忆端口规范（MemoryPort v1）
- `chat-agent-memory-hooks.md` — Recaller/Recorder/Forgetter 协议
- `chat-agent-memory-selection.md` — 检索后端选型（A 词法 → B 网关向量 → C Qdrant）
- `chat-agent-timeline-design.md` — 时间线
- `relationship-state-design.md` — 关系状态
- `chat-agent-context-design.md` — 上下文与会话锁（fence）
