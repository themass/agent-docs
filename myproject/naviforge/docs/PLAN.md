# NaviForge Agent 重构计划（诚实版）

> 更新：2026-09-30  
> 目的：说清楚 **已经改了什么、没改什么、接下来按什么顺序做**，避免「Pi 换核」「智能 Agent」等名不副实的说法。

---

## 1. 之前容易误导你的地方（直说）

| 说法 | 实际情况 |
|------|----------|
| 「用 Pi 替换 loop」 | **没有**引入 Pi 包，**没有**拷贝 `pi/packages/agent` 的 `runLoop`。只是把 `runAgentLoop` **改名为** `runPiAgentLoop`，轨迹里加了一句 `LOOP: pi runLoop`。 |
| 「第 1 期完成」 | 只做了 **PAGE STATE + prepareNextTurn + 登录页禁止重复 dom_read links**。Intent / Skill / Tool 面 **没动**。 |
| 「专业 browser agent」 | 仍缺：**单一路径交付、验证门、真 Pi 或等价瘦 loop**。 |

若你按 PLAN 以为「内核已是 Pi」，那是 **文档和实现不一致**——本节就是校正。

---

## 2. 问题清单（为什么要重构）

按严重度，不是按文档章节。

| # | 问题 | 表现 | 根因在哪 |
|---|------|------|----------|
| P0 | **任务类型判错** | 「生成 Python 抓分类」→ `media_extract` + MEDIA_ENTRY + catalog spawn | `task-intent.ts` 里「视频」优先于「脚本/分类」 |
| P0 | **Preflight 打架** | 同一 run 灌 media-extract + catalog-crawl-sop + 十几条 GUIDANCE | `PreflightHook` + `builtin-hooks` 并行开多条 SOP |
| P0 | **观测薄** | SPA 上 dom_read links 只有登录链接 | 依赖 a11y/链接；PAGE STATE 刚加，**未**替代 preflight 轰炸 |
| P1 | **Tool 面过宽** | catalog ~40 个 model 工具，选择方差大 | `agent-tools.ts` + resolver，未收敛 |
| P1 | **Skill 与任务不对齐** | 脚本任务仍加载 media/catalog skill | preflight 按 intent 正则，无 `script_authoring` |
| P1 | **收尾无验证** | dedupe 强制 system_done，常无 script_save | `DedupeObservationHook` / 无 Verify 门 |
| P2 | **Pi 未真集成** | 无 prepareNextTurn 与 compaction/steer 的 Pi 契约 | 仅 NaviForge 自写 `prepareNextTurn` |
| P3 | **Host harness** | 可选 CDP，与扩展主路径无关 | 排期在交付闭环之后 |

---

## 3. 已经落地的改动（可 grep 验收）

| 改动 | 文件 | 作用 |
|------|------|------|
| `prepareNextTurn` / `attachPageState` | `pi-run-loop.ts` | 每 model turn 前 + preflight 末：wait + snap + PAGE STATE |
| PAGE STATE 分类 | `page-state.ts` | role=login/list/home…；prompt 块 `page_state` |
| 登录页 skip dom_read links | `LoginLinkReadHook` | `builtin-hooks.ts` |
| **阶段 A** Deliverable + script intent | `deliverable.ts`, `task-intent.ts` | 「生成 Python」→ `script` / `script_authoring`；压过「视频」→ media |
| **阶段 A** Preflight 单叙事 | `PreflightHook` | 只 load `scraper-script-sop`；跳过 media recipe / catalog SOP / full-catalog |
| **阶段 B** 登录墙 HITL | `ScriptDeliverableStepHook`, `ScriptLoginNavigateHook` | login + script → ask_user；禁止 dom_navigate 碰运气 |
| TaskHint / classifier | `task-classifier.ts` | script 任务不再灌 catalog/MEDIA 并行 GUIDANCE |
| **阶段 C** 交付验证 | `DeliverableVerifyHook`, `ToolStateHook`, `DedupeObservationHook` | script 无 `script_save` 阻断空 `system_done`；media 无 URL 须 shortfall |
| **通用 in_page 底座** | `execution-task.ts`, `agent.ts` | preflight 前 `ensureAnchorTask` + `taskAnchor`；`lockDeliverable`；**已移除 intake 阶段** |
| **Perceive** | `pi-run-loop.ts` discover 回填 PAGE STATE | `discoverCatalogPage` 补 SPA 列表/分类 |
| **Policy** | `task-scope.ts` | script 任务默认 `navigation: allowed` |
| **Network 默认** | `workspace-run.ts`, `taskRequiresNetworkPlane` | media/script/data 任务自动开 network plane（单次 run） |
| Intake | — | **已删除**（2026-10）；澄清走 `system_ask_user` + THREAD |
| 自测 | `execution-task.self-check.ts` 等 | intake 漂移 + A/B 金句 |

**仍未改：** 真 Pi（E）、harness（F）。

阶段 D ✅（2026-09-30）：model-facing **13** 个正交工具（`browser_observe` / `browser_act` / `browser_nav` / `tabs` / `web_search` / `fetch_text` / `network` / `workspace` / `skill_load` / spawn / done / ask_user / captcha_wait）。旧原子 id 留在 resolver + playbook。Bundled skill 收成 **observe / harvest / traverse / friction / persist / research**；旧 id 为 L1 隐藏别名。KERNEL 只留不变量，不再点 skill 名。

---

## 4. 重构分阶段（新顺序，一条主线）

**原则：** 每期有 **可 grep / 可跑 trace 的验收**；每期做完再开下一期。

### 阶段 A — 单任务单叙事 ✅（2026-09-30）

（内容同下表；验收见 `npm run check -w @naviforge/runtime` 内 `preflight-phase-ab.self-check.ts`。）

| 项 | 做什么 |
|----|--------|
| A1 | 新增交付类 `Deliverable`：`script` \| `data` \| `media` \| `summary` \| `research`（规则 + 自测句） |
| A2 | **「生成 python/脚本/scraper」→ script**，且 **压过** `isMediaTask` 的「视频」 |
| A3 | Preflight **只**加载与该 Deliverable 对应 **一个** skill（脚本类：`scraper-script-sop`，**不** load media-extract / 不全量 catalog spawn） |
| A4 | `intentGuidanceNotes` / catalog preflight **按 Deliverable 分支**，删掉冲突 GUIDANCE |

**验收：** 用 `tests/message.txt` 原任务 → **不得出现** `intent=media`、不得 load `media-extract`、不得 `full-catalog` preflight；**已**用自测模拟通过。

---

### 阶段 B — 页面状态当真 ✅（2026-09-30）

| 项 | 做什么 |
|----|--------|
| B1 | preflight **不再**对 script 任务跑 full-catalog crawl |
| B2 | navigate 后 wait + PAGE STATE + preflight 末 `attachPageState` |
| B3 | role=login + script：**默认** `system_ask_user`；`dom_navigate` 在 login 上 skip |

**验收：** 登录页：PAGE STATE role=login；hook 级自测 ask_user + skip navigate。**端到端**仍依赖扩展 reload 后重跑同一任务 trace。

---

### 阶段 C — 交付验证 ✅（2026-09-30）

| 项 | 做什么 |
|----|--------|
| C1 | `DeliverableVerifyHook`：script 须 `script_save`；media 须 URL 或 shortfall |
| C2 | script deliverable 下 dedupe 不再逼空 `system_done` |

**验收：** hook 级自测 + 扩展 reload 后 trace 应见 blocked `system_done` 或成功 `script_save`。

---

### 阶段 C′ — 通用 in_page 底座 ✅（2026-09-30）

| 项 | 做什么 |
|----|--------|
| P1 | Preflight **在 deliverable 锁定后**（`taskAnchor` + anchor） |
| P2 | `lockDeliverable`（`taskAnchor` 续跑） |
| P3 | media/script/data 自动 enable network（扩展单次 run） |
| P4 | PAGE STATE + catalog discover 回填 |

---

### 阶段 D — Tool / Skill / Prompt 面收敛 ✅（2026-09-30）

**目标：** model-facing 工具 **≤15 正交**；bundled skill 为通用能力；KERNEL 不点 skill 名。

| 项 | 做什么 |
|----|--------|
| D1 | catalog 决策：observe/act/nav/tabs/network/workspace |
| D2 | `AGENT_TOOL_CATALOG` 仅 13 个；旧 id → `expandAgentToolCall` |
| D3 | bundled L1 = 6 能力；别名 `aliasOf` 不进 L1 |
| D4 | KERNEL 瘦身为不变量 + spawn 协议 |

**验收：** `modelFacingToolIds().length <= 15`（self-check）；`npx tsx scripts/export-prompt-tool-skill-doc.ts`。

---

### 阶段 E — L2 演化（进行中，对齐 AGENT_KERNEL §5.5）

| 项 | 做什么 | 状态 |
|----|--------|------|
| E0 | 移除 intake；`taskAnchor` + THREAD 续跑 | ✅ |
| E1 | **PageState-first prompt**：登录/阻塞页不嵌 a11y 树；列表页用 compact snapshot | ✅ `resolveSnapshotPromptPolicy` |
| E2 | Preflight 单叙事：deliverable 锁定时不再叠 intent GUIDANCE | ✅ |
| E3 | 合并重复 hook / Plan 里程碑（减 GUIDANCE 河） | ✅ `deliverablePlanMilestone` + 锁定 deliverable 时跳过 intent/listHint |
| E4 | messages[] 投影（可选）或真 Pi loop | 延后（目标范围外） |

**不要写「已换 Pi」除非做完 E4 真接 Pi 包。**

### 阶段 E（旧表 — 二选一参考）

| 选项 | 含义 | 工作量 |
|------|------|--------|
| **E1 演化** | 保留 `runModelTurns`，删掉/合并 700 行 hook 里与 A/B 重复部分；保留 `prepareNextTurn` | 中 |
| **E2 真接 Pi** | 依赖 `@earendil-works/pi-agent-core`（或 vendored 适配层），NaviForge 只实现 **tools adapter + planes** | 高 |

**当前状态 = 阶段 E 步骤 1–3 + E3 里程碑**；E4（真 Pi / messages[] 全量投影）延后。

---

### 阶段 F — Host browser-harness（可选，最后）

扩展默认不变；Host 可选 CDP provider；与扩展 **互斥写 tab**。见 `AGENT_KERNEL_INTEGRATION_DECISION.md`。

---

## 5. 你现在该看什么

| 若你关心 | 看 |
|----------|-----|
| 总规划（本文） | `docs/myproject/naviforge/docs/PLAN.md` |
| **Prompt / Tool / Skill 全文** | [`AGENT_PROMPT_TOOL_SKILL_CATALOG.md`](./AGENT_PROMPT_TOOL_SKILL_CATALOG.md) |
| 集成 harness / 换不换 L2 | `AGENT_KERNEL_INTEGRATION_DECISION.md` |
| 四层 Perceive/Plan（长期） | `BROWSER_AGENT_NORTH_STAR.md`（**未实现**，是方向） |
| 第 1 期实际代码 | `page-state.ts`、`pi-run-loop.ts`、`LoginLinkReadHook` |

---

## 6. 建议的下一步（开发顺序）

1. **扩展 reload**，用两个 golden case 跑 E2E trace。  
2. **E / F** 按资源排。

---

## 7. 状态

| 日期 | 说明 |
|------|------|
| 2026-09-30 | 诚实版计划；纠正「Pi 换 loop」表述 |
| 2026-09-30 | **A+B+C+C′ 已落地**；D～F 未做 |
