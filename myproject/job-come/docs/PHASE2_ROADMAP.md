# JobCome Phase 2+ 路线图

| 版本 | 1.0 |
| 日期 | 2026-09-04 |
| 前提 | Phase 1（W4–W6 Agent 打穿）代码已合入，待内测验收 |

---

## Phase 1 回顾（当前代码状态）

| 能力 | 状态 |
|------|------|
| Agent 工作台（左场景 + 右流式面板） | ✅ |
| MCP 七工具 + apply_pipeline + question_upsert | ✅ |
| Patch 确认流 | ✅ |
| 会话消息落盘 + builtin hydrate | ✅ |
| 五维 mock rubric + 题库 best_score | ✅ W6 |
| Langfuse LiteLLM callback（配 Key 即启用） | ✅ W6 |
| apply-pipeline 漏斗 JSON 日志 | ✅ W6 |

**内测口令（验收清单）：**

1. 简历 Agent 改档案 → 确认卡片 → version+1  
2. 刷新续聊（同 session_id）  
3. `/apply-agent?job_id=` 走完 fit / patch / pipeline  
4. 模拟面答一题 → `/bank` 见题目 + 最佳分  

---

## Phase 2 — 增长就绪（约 4–6 周）

目标：**可内测、可观测、可演示完整漏斗**，仍不代投。

### P2-A 体验闭环（2 周）

| 项 | 交付 | 优先级 |
|----|------|--------|
| 战役看板 UI | `/campaign`：warmup / target 列表、解锁条件 | P0 |
| 简历多版本对比 | 同 profile 多 `ResumeDraft` diff 视图 | P1 |
| 题库详情页 | 单题 attempt 历史 + 五维雷达图 | P1 |
| Agent 会话列表 | 按 profile 查看历史 session，切换续聊 | P1 |
| 真 LiteLLM 流式 | builtin `stream=True` + tool delta 解析 | P1 |

### P2-B 内容与质量（2 周）

| 项 | 交付 | 优先级 |
|----|------|--------|
| noamseg rubric 深化 | STAR 追问模板、行业 follow-up 库 | P1 |
| resume-reviewer 门禁 | Agent 导出前强制 reviewer tool | P1 |
| 回归集扩充 | 10 JD + 5 简历 + mock 对话 golden | P0 |
| Playwright 导出 E2E | CI 校验 PDF 页数/关键字 | P2 |

### P2-C 观测与运维（1 周）

| 项 | 交付 | 优先级 |
|----|------|--------|
| Langfuse Dashboard | scenario / skill / funnel 看板 | P1 |
| 告警 | apply_pipeline 失败率、LLM 5xx | P2 |
| `scripts/healthcheck.sh` | MySQL + Redis + LLM ping | P1 |

---

## Phase 3 — Scout 与外部源（约 4 周）

目标：**发现岗位**，仍只读、不代投。

| 项 | 说明 |
|----|------|
| boss-agent MCP | `extensions_config` 启用，只读 JD 拉取 |
| tavily / 搜索 | JD 补全与公司 research（可选） |
| Scout 页 | 收藏 → parse → fit 一键进 apply-agent |
| 岗位去重 | 同 company+title 合并 |

---

## Phase 4 — 商业化预备（约 4 周，可选）

| 项 | 说明 |
|----|------|
| 付费墙 | 导出次数 / mock 轮数 / LLM 额度 |
| 中英双轨 | locale 模板 + 拔高 prompt 分支 |
| B 端试点 | 高校就业中心席位 |
| 合规 | 个保法删除 SLA、隐私政策页 |

---

## Phase 5 — 超越「求职工具」（战略选项）

这些是 **产品形态升级**，与 ai-job-search 对齐但面向 C 端长期留存：

### 5.1 陪伴式 Coach（非单次任务）

- 周计划：本周投 2 个 target + 3 次 mock  
- 推送：面经到期复习、弱项维度提醒  
- 记忆：「上次字节面挂在项目量化」跨 session 引用  

### 5.2 多模态面（LiveKit / 语音）

- 实时语音 mock，同一 `coach-mock` skill + ASR/TTS  
- 面后自动 transcript → `answer_save_attempt`  

### 5.3 社区飞轮（Q2 产品设计）

- 脱敏真题贡献、可撤回  
- 社区 rubric 投票，个人库与社区库分层  

### 5.4 Agent 编排升级（可选替换 harness）

- DeerFlow 子图：writer / reviewer 分离  
- 长对话 compaction（保留 skill + 最近 N 轮 + 档案摘要）  
- 多 Agent 并行：Scout agent + Coach agent 分工  

### 5.5 数据智能

- Fit 校准闭环：用户标记「进面/挂」→ 重训权重  
- 行业 salary / level 基准（仅展示，不承诺）  

---

## 建议执行顺序（接下来 2 周，无需你在线）

```text
Week A   战役看板 UI + Agent session 列表 + 题库详情
Week B   真 LLM 流式 + Playwright export CI + 回归集扩充
```

---

## 原则（延续）

1. **不代投** — Scout 只读，apply 必须用户确认  
2. **真相源** — Profile / Job / Interview 只经 MCP/Service  
3. **Agent 是编排入口** — 不复制 REST 流水线第二套引擎  
4. **可观测先行** — 每个 funnel step 有 `jobcome.events` + Langfuse trace  

---

## 相关文档

- [ROADMAP.md](./ROADMAP.md) — 周计划总表  
- [Agent核心能力规划.md](./Agent核心能力规划.md) — G1–G4 目标  
- [可观测性与Trace.md](./可观测性与Trace.md) — Langfuse 配置  
