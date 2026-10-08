# NaviForge 专业浏览器 Agent — 战略蓝图

> **性质**：产品 + 架构北极星（不是 PR 清单）  
> **立场**：当前实现 **尚不具备**「专业浏览器 Agent」资格；本文定义要变成什么、为何比通用 Agent 更强、如何分阶段落地。  
> **集成 / 换内核（必读）**：[AGENT_KERNEL_INTEGRATION_DECISION.md](./AGENT_KERNEL_INTEGRATION_DECISION.md) — browser-harness-js、browser-use、Pi 等 **同一张表**。  
> **战术拆解**：[SCRAPER_AGENT_RELIABILITY_PLAN.md](./SCRAPER_AGENT_RELIABILITY_PLAN.md) 仅覆盖其中一条用户路径的止血，**不能替代本文**。  
> **实现权威（现状）**：[AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)

---

## 1. 直说现状：为什么连通用 Agent 都比不过

通用 Agent（Cursor、ChatGPT、Claude + 搜索）在「分析网站、写脚本、给方案」上往往更强，原因不是模型更大，而是 **目标函数简单**：

| 通用 Agent | 当前 NaviForge |
|------------|----------------|
| 读用户描述 + 可选网页摘要 → **直接交付**（代码/步骤） | 必须先走 **tool 循环**，且被 preflight **强行绑定** media/crawl SOP |
| 没有「每轮只能一个 tool」+ 39 个工具的 **选择方差** | 模型在 dom_read / navigate / spawn 间 **空转** |
| 失败时 **换说法再答** | dedupe / friction / HITL **截断** run，且常 **无交付物** |
| 不假装「已在浏览器里抓到了流地址」 | 却在 **network off** 时仍走 media recipe → 必败 |

**专业浏览器 Agent 的唯一正当性**：在用户 **真实 Chrome 会话** 里，做到通用 Agent **做不到或做不好** 的事——且 **可验证**。  
若做不到，就应诚实降级为「带侧栏的 LLM + 页面工具箱」，而不是挂「Agent」名头。

当前 gap 的本质：**编排层在替模型「聪明」**（intent 正则、catalog preflight、spawn 子 Agent），但 **感知层给的数据太差、规划层缺失、验证层几乎为零**，结果既不如通用 Agent 能写代码，又不如 Playwright 脚本可靠。

---

## 2. 专业浏览器 Agent 的产品契约（对外承诺）

对用户可感知的能力，必须满足下面 **四条契约**（否则不算「专业」）：

### C1 — 看见真实页面，不是看见登录壳

- 输出任何「站点结构 / 列表 / 脚本」前，系统必须持有 **PageState 快照**：当前 URL、页面角色（home/list/detail/login）、**可验证的** 列表条目或 API 线索、摩擦状态。
- **禁止** 在「仅 login 表单链接、0 条列表」状态下进入「分析完成」或 `system_done` 声称已理解站点。

### C2 — 任务类型决定 **交付形态**，不是决定 **媒体 SOP**

| 用户要什么 | 交付物 | 浏览器特有证据 |
|------------|--------|----------------|
| 爬虫 / 脚本 / 批量列表 | **可运行代码 + 参数说明**（`script_save` / Host） | 真实 URL 模式、分页、可选 XHR 样例（脱敏） |
| 单页理解 | 摘要 + 引用 | dom_read body / PDF |
| 媒体地址 | mediaUrl 或 shortfall | network + 播放路径 |
| 多源对比 | 表格/报告 | tabs + fetch |

**一条任务只有一个主交付类型**；runtime 不得再同时灌 media spawn + catalog 全站 + script 三套 narrative。

### C3 — 每一步可验证，结束可复盘

- 每个 Act 步有 **Check**：导航后 URL 是否变化、列表条数是否 >0、脚本是否 dry-run 语法通过。
- Run 结束必须 **Pass 验证门** 或 **结构化失败**（缺什么、用户下一步做什么），不能「模型说完成了」。

### C4 — 比通用 Agent 多出来的必须是 **会话级能力**

至少稳定提供其中 **两项** 作为 moat：

1. **已登录会话**下的结构分析（用户手动登录，Agent 读同一 cookie jar）  
2. **Network 摘要**下的 API 发现（XHR 列表接口，而非猜 DOM）  
3. **操作录制 → Playbook / Recipe** 确定性重放  
4. **Host** 上脚本执行、ffmpeg、文件落盘  

通用 Agent 没有 1–4；若 NaviForge 也不默认打通 1–2，就 **没有资格** 主打「浏览器专业」。

---

## 3. 目标架构：四层智能，而不是「Hook 堆叠的 Tool Loop」

```text
                    ┌─────────────────────────────────────┐
                    │  User task + Thread memory          │
                    └──────────────────┬──────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ L1  PERCEIVE  「页面理解服务」—  deterministic + 可选 LLM 摘要      │
│  PageState = { url, role, friction, items[], apis[], signals[] } │
│  来源：snapshot + discover JS + network digest + friction        │
│  **每轮 Act 前刷新**；整包注入 working set（模型不再盲 dom_read）   │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ L2  PLAN      「任务规划器」— 显式 Plan 对象，非长 GUIDANCE 文本      │
│  milestones: 进入公开页 → 发现分类 → 采样 1 页 → 写脚本 → 验证     │
│  主 intent 一条；工具预算；失败分支（开 Network / ask_user）         │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ L3  ACT       「窄工具执行器」— model-facing ≤12 正交工具           │
│  navigate / interact / read(state) / network(query) / workspace   │
│  禁止：与 PageState 重复的 raw dom_read 试探                         │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ L4  VERIFY    「验证门 + 交付」                                     │
│  script: lint + optional Host dry-run                              │
│  crawl: 条目数 / URL 可达                                         │
│  media: candidate 在 network 或 signals 中存在                      │
│  不过门 → replan 或 structured shortfall，**禁止** 空 system_done   │
└──────────────────────────────────────────────────────────────────┘
```

### 与现状对照（必须改掉的结构）

| 现状 | 目标 |
|------|------|
| `resolveTaskIntent` 正则 + 大量 GUIDANCE 文本 | **Plan 对象** + 里程碑状态机 |
| preflight 里 catalog/media/friction 并行 | **Perceive 一次** → Plan 选路径 |
| 模型自己选 dom_read mode | **`page_state` 工具 / 块** 返回结构化 PageState |
| `builtin-hooks` 700+ 行纠偏 | **Verify 门** + 少量 policy hook |
| 39 catalog tools | **≤12** model-facing；其余 handler 内部 |

---

## 4. L1 Perceive：浏览器 Agent 的「眼睛」（最高优先级）

**原则**：感知是 **代码责任**，不是 **prompt 责任**。

### 4.1 PageState（新核心类型，单源）

建议字段（实现可迭代）：

```ts
type PageState = {
  url: string
  title: string
  role: 'unknown' | 'login' | 'home' | 'list' | 'detail' | 'player' | 'error'
  friction: { blocking: boolean; kinds: string[] }
  navigation: { sections: { label: string; href: string }[] }
  listPreview: { title: string; url?: string }[]  // cap N
  networkHints: { method: string; pathPattern: string; sampleStatus?: number }[]
  pagination?: { style: 'query' | 'path' | 'button'; pattern?: string }
  confidence: number
  shortfall?: string
}
```

**生成管线**（extension + runtime，每轮 Act 前 / navigate 后）：

1. `dom_wait`（url stable / network idle 轻量）  
2. 已有 `CATALOG_DISCOVER_JS` + `page-friction` + `collect_page_signals` **合并**  
3. 若 `networkEnabled`：`network_plane` digest **最近 30s XHR** 过滤静态资源  
4. 输出 **一条** `run.page_state` trace + working set 块 `PAGE STATE:`

### 4.2 对模型的接口

- 新增 **`page_state` 只读工具**（或每轮自动注入，工具仅 `refresh: true`）  
- **废弃**「先 dom_read links 摸结构」作为默认路径；KERNEL 改为：**先读 PAGE STATE，再 Act**

### 4.3 验收

- 任意 SPA mock：PageState.listPreview.length ≥ 1 或 networkHints 非空  
- login 页：role=login + shortfall，**blocking 仅当任务需要列表且 0 证据**

---

## 5. L2 Plan：从「Intent 正则」到「可执行计划」

### 5.1 主任务分类（少量、互斥）

| Class |  Planner 模板 |
|-------|----------------|
| `DELIVER_SCRIPT` | 采样结构 → 写 py/js → Host/workspace 验证 |
| `DELIVER_DATA` | 列表 extract → 可选 spawn → JSON/CSV |
| `DELIVER_MEDIA` | signals → network → click 播放 |
| `DELIVER_SUMMARY` | read body → done |
| `DELIVER_RESEARCH` | search → tabs → compare |

分类可用 **轻量 LLM 一次** 或 **规则 + LLM 复核**；关键是 **输出 Plan JSON**，不是 15 条 GUIDANCE。

### 5.2 Plan 对象

```ts
type RunPlan = {
  class: 'DELIVER_SCRIPT' | ...
  milestones: { id: string; done: boolean; evidence?: string }[]
  toolBudget: number
  requiresNetwork: boolean
  deliverable: 'script' | 'markdown' | 'json' | 'media_entry'
}
```

- Preflight **只** 生成 Plan + 跑 Perceive  
- Skill 按 **Plan.class** 加载 **一篇** SOP  
- 子 Agent spawn **仅** Plan 明确 `parallel_samples > 0`

### 5.3 与用户 session 的修复

你的失败 case：`DELIVER_SCRIPT` Plan 不应加载 media-extract / MEDIA_ENTRY / full-catalog spawn。

---

## 6. L3 Act：窄而深的工具面

### 6.1 Model-facing 工具（目标 ≤12）

| 工具 | 职责 |
|------|------|
| `page_state` | 读/刷新 PageState |
| `page_navigate` | url / back / reload + 内置 wait |
| `page_interact` | click / type / scroll（index 来自最新 state） |
| `page_extract` | list/body/markdown（参数化，一种入口） |
| `network_query` | digest / wait_for / match（需开关） |
| `fetch_text` | 离页静态 |
| `tabs_*` | 研究模式 |
| `workspace_*` | 写文件、script_save |
| `system_*` | done / ask / captcha / spawn（受 Plan 约束） |
| `skill_load` | 渐进披露 |
| `web_search` | research |
| `mcp__*` | 授权扩展 |

内部仍可保留 page-controller 细粒度 handler；**catalog 不对模型暴露 20 个别名**。

### 6.2 Act 规则

- index 绑定 **PageState revision**（已有 snapshot revision，需与 PageState 同步）  
- navigate 后 **自动 Perceive**；模型无需再调 dom_navigate 两次  
- Plan.class=SCRIPT 时 **禁止** spawn media 子任务（policy 硬拦）

---

## 7. L4 Verify：专业与业余的分水岭

| 交付类型 | 验证 |
|----------|------|
| script | 语法检查；可选 Host `python -m py_compile`；Plan 里程碑全 ✓ |
| data | 条目数 ≥ 用户阈值或 shortfall |
| media | URL 在 signals/network 出现过 |
| summary | 引用 PAGE STATE / body 长度 |

**禁止**：dedupe 触发 → 无验证的 `system_done`。改为：

- `replan`（换 milestone：开 Network / ask_user）或  
- `system_done` **仅带** shortfall + 部分交付（骨架脚本）

---

## 8. 通用 Agent 打不过我们的条件（Moat 清单）

必须 **产品化** 而非「文档里提到」：

| Moat | 用户动作 | 系统行为 |
|------|----------|----------|
| **会话继承** | 用户先登录，再 Run | PageState 在 login 后自动 refresh；Plan 从 milestone 2 继续 |
| **API 发现** | Advanced 开 Network | PageState.networkHints + script 里 `requests.get(api)` 模板 |
| **可重放** | Run 成功 | 一键 Forge Playbook / Site Recipe |
| **本地执行** | 装 Host | script 真跑、ffmpeg、写盘 |
| **审计** | 开发者 | 完整 trace + PageState 时间线 |

**若 1–2 默认不可用且 UI 不引导**：对外应改文案为「页面助手」，直到 Perceive+Network 路径打通。

---

## 9. 评测体系（没有评测就没有「智能」）

### 9.1 NaviForge Browser Bench（NBB）

分级：

- **L0** 静态 HTML（本地 fixture）— 结构 / 脚本  
- **L1** 公开 SPA mock（e2e server）— PageState + 分页  
- **L2** 需登录 mock — friction + 用户 HITL 模拟  
- **L3** 真实站（脱敏 trace 回放，不 CI 外联）

每条用例：**输入 task → 期望 deliverable 类型 → 自动 scorer**（脚本存在？条目数？）。

### 9.2 与通用 Agent 对照

同 prompt 跑：

- NaviForge（扩展）  
- Cursor（无浏览器 / 有浏览器若可用）  

记录：**交付率、步数、正确性**。专业 Agent 在 **L1–L2 + 会话/Network** 必须 **显著高于** 通用，否则战略失败。

### 9.3 CI

- `npm run check` + NBB L0/L1 headless  
- 每周人工 L2 抽检

---

## 10. 分阶段落地（三 horizon）

### Horizon A — 「能交付」（0–3 个月）：没有 PageState 不要谈智能

| 里程碑 | 内容 |
|--------|------|
| A1 | **PageState 管线** + `run.page_state` + working set 注入 |
| A2 | **Plan 对象** 替代 intent+GUIDANCE 堆叠（5 class） |
| A3 | Navigate→wait→Perceive **硬编码** |
| A4 | **Verify 门** + script/data 交付规则 |
| A5 | NBB L0/L1 + 你的 G1 用例进 CI |
| A6 | UI：脚本类任务 **引导 Network**（非默认全开） |

**退出标准**：G1 类任务 **80%** 产出可编译脚本或 structured shortfall；**0%** media intent 误判。

### Horizon B — 「比通用 Agent 强」（3–6 个月）

| 里程碑 | 内容 |
|--------|------|
| B1 | Model-facing 工具收敛到 **≤12** |
| B2 | Planner 可选 **小模型一次**（class + milestones） |
| B3 | Network digest → **API 模板** 自动写入 script 注释 |
| B4 | Site Recipe / Playbook 从 Plan 成功路径 **一键生成** |
| B5 | NBB L2 + 对照实验报告（对内） |

### Horizon C — 「专业平台」（6–12 个月）

| 里程碑 | 内容 |
|--------|------|
| C1 | 多 tab 研究编排（只读子 Agent 受 Plan 约束） |
| C2 | Host 可选 CDP 桥（browser-harness 类 **仅 Host**） |
| C3 | 站点 Pack（社区 Recipe + PageState 启发式） |
| C4 | 企业：审计导出、策略模板 |

---

## 11. 必须删除或降级的「伪智能」

否则新架构会被旧 hook 拖死：

1. **并行冲突 preflight**（media + catalog 全量 on 同一 run）→ 删，改为 Plan 单路径  
2. **15+ 条 GUIDANCE 轰炸** → 缩为 Plan milestones 状态  
3. **regex intent 优先级**（视频词压过脚本）→ 归入 Plan class DELIVER_SCRIPT  
4. **无验证 system_done** → Verify 门硬拦  
5. **对壳页 dom_read 循环** → PageState shortfall 一次说清  
6. **catalog 全站 crawl 作为 preflight 默认** → 仅 DELIVER_DATA 且 Plan 要求时  

---

## 12. 组织与文档

| 文档 | 角色 |
|------|------|
| **本文** | 北极星 + horizon |
| AGENT_SYSTEM_DESIGN.md | 随 A1–A4 **重写**「当前实现」章节 |
| SCRAPER_AGENT_RELIABILITY_PLAN.md | 并入 A 阶段验收条目后 **归档** |
| ARCHITECTURE_OPTIMIZATION.md | 工具收敛对齐 §6 |

建议 **单轨负责人**：Runtime 编排 + extension Perceive 胶水（同一人避免 plane 分裂）。

---

## 13. 对你这句话的回应

> 就现在这个样子，连个通用 agent 都比不上，有什么资格做专业的浏览器 agent

**结论**：**目前没有资格**；资格不来自更多 tool 或更多 skill，而来自：

1. **每轮都给模型一份可信的 PageState**  
2. **任务结束必有一种可验证交付**  
3. **在会话 + Network 场景系统性赢通用 Agent**  

做到 Horizon A 的 A1–A5，才配继续叫 **Browser Agent**；否则应改产品叙事为 **「Chrome 里的 LLM 工作台 + 工具箱」**，避免用户预期崩盘。

---

## 14. 状态日志

| 日期 | 说明 |
|------|------|
| 2026-09-30 | 初版战略蓝图（用户要求「不是小改，要智能 Agent」） |
