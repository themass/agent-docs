# NaviForge 站点分析 / 爬虫脚本 Agent 可靠性计划

> **状态**：执行计划（2026-09-30，由 `tests/message.txt` session 复盘驱动）  
> **读者**：Runtime / Extension 维护者、产品  
> **关联**：[ARCHITECTURE_OPTIMIZATION.md](./ARCHITECTURE_OPTIMIZATION.md)、[RELEASE_PLAN_B.md](./RELEASE_PLAN_B.md)、[AGENT_SYSTEM_DESIGN.md](./AGENT_SYSTEM_DESIGN.md)（若存在）

---

## 1. 背景：这次失败说明了什么

用户任务（典型）：

> 分析这个网站的视频列表，给我生成一个 Python 脚本，抓取每个分类下的第一页。页码可配置，默认 1。

Session trace（`tests/message.txt`，run `518098c9…`）暴露 **四类系统性问题**，不是单次模型抽风：

| # | 问题 | 证据 |
|---|------|------|
| A | **Intent 判错** | 含「视频」→ `media_extract` 优先于「每个分类」→ `multi_hop_crawl` |
| B | **Preflight 打架** | 同时灌 media-extract + catalog-crawl-sop + MEDIA_ENTRY spawn |
| C | **观测带宽不足** | `dom_read(links)` 仅登录页链接；SPA 列表未进 a11y；network plane 关 → recipe 失败 |
| D | **收尾机制误伤** | 无证据时 dedupe 强制 `system_done`；504 中断；未走 `script_save` |

**产品承诺 vs 运行时目标函数不一致**：用户要 **可运行 `.py` + 真实 URL/API 模式**；系统在优化 **mediaUrl / 子任务 spawn**。

---

## 2. 目标与成功标准

### 2.1 北星（North Star）

在 **用户已打开目标站点的标签** 上，对「结构分析 + 生成爬虫脚本」类任务：

1. **一次 Run 内** 交付 `scripts/` 或 workspace 下的 **Python 文件**（经 `script_save`），或  
2. **明确 shortfall**（需登录 / 需开 Network / 需用户指定公开入口 URL），并仍给出 **带 TODO 的脚本骨架**。

### 2.2 可验收指标（Release gate）

| 指标 | 阈值 |
|------|------|
| Golden task 通过率 | ≥ **4/5** 固定用例（见 §7）在 `npm run check` + 本地扩展跑通 |
| Intent 回归 | `task-intent.self-check` + 新增 `script_authoring` 用例 **100%** |
| 错误 intent 率（golden） | **0%** media_extract 误判脚本任务 |
| 平均 tool 步数（golden SPA） | ≤ **12** 步到 `script_save` 或 structured shortfall |
| 空转 dom_read 重复 | 同 URL+同 args **≤ 1** 次（dedupe 后必须换策略或 done） |
| Trace 可复盘 | 每条 golden 保留 anonymized fixture JSONL |

### 2.3 非目标（本计划不做）

- 破解 DRM / 绕过付费墙 / 批量下载侵权内容（仍走 `denied` + 合法 shortfall）
- 把 Playwright 打进 MV3 主包
- P5 全托管云
- 自动从 Run 生成 Skill（仍仅 import）

---

## 3. 设计原则（后续改动的约束）

1. **单一主 Intent 驱动 preflight** — 禁止同一 turn 加载互斥 SOP（media 全量 spawn vs script 交付）。
2. **证据先于循环** — catalog discover / page_signals / network 摘要 **写入 working set**，模型第一步应 **读 evidence**，不是盲 `dom_read links`。
3. **Navigate 即契约** — `dom_navigate` 后必须 **wait + snap 刷新** 再 friction / read。
4. **完成定义与工具对齐** — 脚本类任务的 done = **`script_save` + system_done 附 path**，不是 MEDIA_ENTRY JSON。
5. **默认 BYOK / 默认 network off 不变** — 脚本任务 **提示** 开 Network，不默认全开（商店合规）。

---

## 4. 阶段路线图（总览）

```text
Phase 0  基线与回放          1 周
Phase 1  Intent 与路由       1 周
Phase 2  Preflight 一致化    1～1.5 周
Phase 3  观测层（SPA/API）   2 周
Phase 4  收尾与摩擦策略      1 周
Phase 5  Golden + E2E + 文档 1 周
────────────────────────────────────
合计约 7～8 周（可并行 Phase 3 部分与 Phase 2）
```

---

## 5. Phase 0 — 基线与回放（P0）

**目的**：可重复复现 `message.txt` 类失败，避免「改完不知道有没有好」。

| ID | 工作项 | 产出 | 主要文件 |
|----|--------|------|----------|
| 0.1 | 将 `tests/message.txt` 脱敏为 **fixture**（URL 可替换为 example.com） | `tests/fixtures/traces/scraper-script-fail.jsonl` | tests |
| 0.2 | **Trace replay 自检**：对 fixture 断言 intent、前 5 条 guidance 关键词 | `packages/runtime/src/trace-replay.self-check.ts`（或脚本） | runtime |
| 0.3 | 文档化 **手动复现步骤** | 本节 §7.1 用例 1 步骤 | 本文 |
| 0.4 | 记录当前 privacy 默认（networkEnabled、allowDomInject、allowDomProbe） | checklist 一行 | extension settings |

**验收**：CI 中 `tsx trace-replay.self-check.ts` 失败于 **当前 main 行为**（红灯），Phase 1 完成后变绿。

---

## 6. Phase 1 — Intent 与任务路由（P0）

**目的**：「生成 Python 脚本 + 列表/分类/抓取」不再被判成 `media_extract`。

### 6.1 新增 Intent

| Intent | 触发（启发式，需 self-check） | Preflight skill |
|--------|------------------------------|-----------------|
| `script_authoring` | `生成.{0,12}(python\|脚本\|scraper)` 或 `(python\|脚本).{0,16}(抓取\|爬\|crawl\|scrape)` | `scraper-script-sop`（新建） |
| 保留 `media_extract` | m3u8/播放地址/源流/下载视频文件（且无 script 触发） | media-extract |

### 6.2 优先级规则（`resolveTaskIntent`）

建议顺序：

1. `denied`
2. **`script_authoring`**（新）
3. `page_download`
4. **`multi_hop_crawl`** if `isCatalogCrawlTask` / `isSiteCatalogSopTask`
5. `media_extract` **仅当** 非 script 且非 catalog 主任务
6. …其余不变

**关键**：`isMediaTask` 中的「视频」**不能**单独压过「每个分类 + 脚本」。

### 6.3 工作项

| ID | 工作项 | 验收 |
|----|--------|------|
| 1.1 | 扩展 `TaskIntent` + `resolveTaskIntent` | self-check 含用户原句 |
| 1.2 | `intentPreflightSkill` / `intentGuidanceNotes` | script 路径无 MEDIA_ENTRY |
| 1.3 | 新建 skill **`scraper-script-sop`**（bundled） | Phase 0→2→save 简短 SOP |
| 1.4 | `task-intent.self-check.ts` 至少 8 条边界句 | `npm run check -w @naviforge/runtime` |

**主要文件**：

- `packages/runtime/src/task-intent.ts`
- `packages/runtime/src/skills/bundled/`（或现有 skill 目录）
- `packages/runtime/src/task-intent.self-check.ts`

---

## 7. Phase 2 — Preflight 一致化（P0）

**目的**：一次 Run 只推 **一条** 主叙事；catalog 只提供 **结构证据**，不自动 spawn 媒体 army。

### 7.1 Preflight 矩阵

| 主 Intent | 加载 skill | catalog preflight | media recipe | spawn MEDIA |
|-----------|------------|-------------------|--------------|-------------|
| `script_authoring` | scraper-script-sop | **discover only** → evidence | ❌ | ❌ |
| `multi_hop_crawl` | catalog-crawl-sop | full / current-page 按 strategy | 仅 `wantsMediaUrl` | 按现逻辑 |
| `media_extract` | media-extract | 可选 | ✅ if network | ✅ |

### 7.2 工作项

| ID | 工作项 | 验收 |
|----|--------|------|
| 2.1 | `builtin-hooks.ts` preflight 分支按 **ctx.gates.taskIntent** 互斥 | trace 中 script 任务无 media-extract preflight |
| 2.2 | `formatCatalogPlanEvidence` / discover 结果 **强制进 working set**（已有则加强） | 模型首 turn 可见 section URLs |
| 2.3 | script intent：**禁止** `MEDIA_AGENT_JUDGMENT_GUIDANCE` 注入 | grep self-check |
| 2.4 | `preflight-synthesize.self-check.ts` 更新 | CI 绿 |

**主要文件**：

- `packages/runtime/src/builtin-hooks.ts`
- `packages/runtime/src/task-classifier.ts`（若需 `isScriptAuthoringTask`）
- `packages/runtime/src/preflight-synthesize.ts`

---

## 8. Phase 3 — 观测层（SPA / API / Navigate）（P0～P1）

**目的**：让「写爬虫脚本」拿到 **URL 模式、列表 API、分页参数**，而不是 login 页 `<a>`。

### 8.1 Navigate 契约

| ID | 工作项 | 说明 |
|----|--------|------|
| 3.1 | `dom_navigate` handler 后 **dom_wait**（networkIdle 或 min delay + url stable） | extension/dom-plane |
| 3.2 | navigate 后 **强制 dom_snapshot / snap.url 刷新** | runtime snap |
| 3.3 | page friction 使用 **刷新后** URL + body | 降低 home→login 误报 |

### 8.2 结构发现（给 script 任务专用）

| ID | 工作项 | 说明 |
|----|--------|------|
| 3.4 | script preflight 跑 `CATALOG_DISCOVER_JS` 或轻量 **site_map** tool 结果进 context | 不必 full crawl |
| 3.5 | 推广 **`dom_read mode=list`** 为脚本任务首选（KERNEL / scraper SOP） | 文档 + prompt |
| 3.6 | **`dom_probe` 白名单路径**（只读 JSON：`__NEXT_DATA__`、`window.__INITIAL_STATE__` 等） | privacy 仍默认 off，guidance 提示开启 |
| 3.7 | **Network 可选摘要**：脚本任务若 network off，run.note 提示「开 Network 可抓 XHR 列表 API」 | 不默认开 plane |

### 8.3 Host 侧（可选 P1）

| ID | 工作项 | 说明 |
|----|--------|------|
| 3.8 | Host 跑通时：`fetch_text` 批量验证脚本内 URL（只读） | 已有 workspace plane |

**主要文件**：

- `packages/dom-plane/`、`apps/extension/src/content/`
- `packages/runtime/src/catalog-crawl/discover.js`
- `packages/runtime/src/tools/handlers/dom*.ts`
- `apps/extension/src/lib/settings.ts`（privacy 文案）

**验收**：对 **mock SPA fixture**（本地 static server in e2e），discover 至少返回 N≥3 个 section links。

---

## 9. Phase 4 — 收尾、dedupe、摩擦（P0）

**目的**：不在「零证据」时强制 success；脚本任务必须 **`script_save` 或 explicit shortfall**。

### 9.1 Dedupe / action-loop

| ID | 工作项 | 规则 |
|----|--------|------|
| 4.1 | `script_authoring`：dedupe 触发后 **禁止空 system_done** | 改为 GUIDANCE：probe / network / ask_user / script_save skeleton |
| 4.2 | 允许 **一次** `dom_execute_js` 只读发现（脚本 intent） | policy 放宽 vs 列表页 media |

### 9.2 Page friction

| ID | 工作项 | 规则 |
|----|--------|------|
| 4.3 | script 任务：login **advisory** 若 snap 含 `/home` 且 discover>0 sections | 减少误 BLOCKING |
| 4.4 | BLOCKING 时优先 **system_ask_user**（指定公开 URL）而非无限 dom_navigate | hooks |

### 9.3 交付

| ID | 工作项 | 规则 |
|----|--------|------|
| 4.5 | scraper SOP：**最少 1 次** `script_save` 才能 `system_done`（除非 user abort） | beforeTool 或 guidance |
| 4.6 | `system_done` 模板含：`filename`、`categories_found`、`pagination_pattern`、`needs_cookie` | skill 正文 |

**主要文件**：

- `packages/runtime/src/action-loop.ts` / `loop-gates.ts`
- `packages/runtime/src/page-friction/`
- `packages/runtime/src/tools/builtin-handlers.ts`（script_save）

---

## 10. Phase 5 — Golden tasks、E2E、文档（P1）

### 10.1 Golden tasks（固定 5 条）

| # | 任务摘要 | 期望 |
|---|----------|------|
| G1 | 用户原句（视频列表 + Python + 每分类第一页） | intent=script_authoring；产出 `.py` 或 shortfall+骨架 |
| G2 | 纯 media：「这个视频的 m3u8」 | intent=media_extract（回归） |
| G3 | 「每个分类前 2 页，JSON 输出」无脚本 | multi_hop_crawl |
| G4 | 「总结当前页」 | page_read |
| G5 | SPA mock（e2e 本地站）脚本生成 | discover≥3 sections |

### 10.2 E2E

- 扩展：`tests/e2e/scraper-script-golden.spec.ts`（Playwright 驱动侧栏或 workspace）
- Runtime：self-check 全覆盖；可选 **headless** dom-plane mock

### 10.3 文档

| 文档 | 内容 |
|------|------|
| 本文 | 维护状态勾选 |
| `AGENT_SYSTEM_DESIGN.md` 或 KERNEL | script vs media 决策表 |
| Options 隐私说明 | 「爬虫分析建议开 Network / Probe」一句 |

**验收**：`npm run check` + `npm run test:e2e`（naviforge 根）绿；G1 人工录屏 1 次存档。

---

## 11. 依赖与风险

| 风险 | 缓解 |
|------|------|
| 真实站点变卦 / 非法内容站 | Golden 用 mock + 脱敏；生产 trace 不提交真实 URL |
| Network plane 增加权限感知 | 仍 opt-in；脚本任务 only **提示** |
| Intent 启发式误判 | self-check + 每周加一条用户失败 trace |
| 504 / 模型超时 | 与本次无关但需 **重试不扣 turn**；已有 HITL continue |
| catalog 与 script 代码分叉 | discover JS **单源**；script 只读 discover 结果 |

---

## 12. 执行顺序（建议 PR 切分）

```text
PR1  Phase 1 — intent + scraper-script-sop + self-check
PR2  Phase 2 — preflight 互斥 + evidence 注入
PR3  Phase 3.1–3.3 — navigate wait + friction 刷新
PR4  Phase 3.4–3.7 — discover/list/probe guidance + network hint
PR5  Phase 4 — dedupe + script_save gate + friction tuning
PR6  Phase 0 + 5 — fixtures + e2e golden + doc 勾选
```

每个 PR：**必须**更新 self-check；**禁止**单 PR 超过 800 行无关改动。

---

## 13. 验收清单（发布前勾选）

- [ ] G1～G5 通过
- [ ] `tests/message.txt` 类 trace replay 显示 intent=script_authoring，无 media spawn guidance
- [ ] 商店默认 networkEnabled 仍为 false
- [ ] THIRD_PARTY / 隐私文案未承诺默认远程调试
- [ ] `RELEASE_PLAN_B` 或本文状态更新

---

## 14. 附录：手动复现 G1（Phase 0）

1. 安装扩展 dev build；配置 LLM；**可选**开 Network（Advanced）。
2. 打开目标站 **已登录或公开 home** 标签；侧栏 Run。
3. 粘贴用户原任务；观察 trace：intent、preflight、首 3 个 tool。
4. 期望（计划完成后）：≤12 步出现 `script_save`；文件可在 workspace 打开。

---

## 15. 状态日志

| 日期 | 变更 |
|------|------|
| 2026-09-30 | 初版计划（自 message.txt 复盘） |
