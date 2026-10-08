# Runtime 工程纪律（通用 Browser Agent）

> 产品定位：**通用** in-tab Agent（读页、抓媒体、写脚本等），不是单站爬虫项目。  
> 内核路线：[AGENT_KERNEL_INTEGRATION_DECISION.md](./AGENT_KERNEL_INTEGRATION_DECISION.md) §5.5。

---

## 1. 禁止 host 分支

**不得在 runtime / extension 业务逻辑里** 用具体站点域名做特判，例如：

- `if (host === 'example.com')` / `url.includes('xzg4q')`
- 为某一站点单独增加的 hook、tool 分支、preflight 短路
- 把验收站 URL 写进 `packages/runtime` 或 `apps/extension`（测试/fixture 除外）

**允许（数据驱动，不是代码分支）：**

- **SiteRecipe**：用户或 bundled **数据** 里的 `hosts: ['*']` 或某 host，由 `findSiteRecipe(host, intent)` 查找；不在 TS 里写死「只对这个 host 怎样」。
- **测试**：`demos/test-site/`、`*.self-check.ts`、E2E 里的 example URL。
- **通用 URL 形态**：`looksLikeLoginUrl(pathname)`、`resolveDeliverable(task 文案)` — 与具体站点无关。

**Review 自检：** PR 若新增 hostname 字面量（除 recipe 测试/fixture），应拒绝或改为 generic 规则。

---

## 2. 新行为必须先写 Deliverable Plan

任何影响 Agent **怎么走任务** 的改动（新 preflight、新 hook 约束、新 deterministic 路径、新 skill 加载策略），**先于代码** 明确：

| 项 | 说明 |
|----|------|
| **Deliverable** | `script` \| `media` \| `data` \| `summary` \| `research` \| `general` — 一次 Run **只有一个** |
| **Plan 步骤** | 3～6 步：Perceive → Act → Verify；写进 `deliverablePlanMilestone()` 或同 deliverable 的 PLAN 注记 |
| **Verify** | 怎样算交卷：`script_save` / mediaUrl / shortfall 模板 |
| **不用什么** | 例如 script Run 禁止 media recipe、禁止 full-catalog spawn |

**代码落点（顺序）：**

1. 更新 `packages/runtime/src/deliverable.ts` — `deliverablePlanMilestone` / `deliverablePreflightSkill` / `lockDeliverable`（若涉及路由）
2. 必要时更新 `docs/BROWSER_AGENT_NORTH_STAR.md` 或本文的 deliverable 表
3. 再写 hook / preflight / extension — hook 只做 **Verify、安全、预算**，不替代 Plan 叙事
4. 加 **deliverable 级 self-check** 或 golden 任务句式（URL 只在测试里）

**反模式：** 先加 `MediaHarvestMilestoneHook` 再补文档；同一 Run 叠 media + catalog GUIDANCE；用 CONSTRAINT 轰炸代替一条 PLAN。

---

## 3. Deliverable Plan 源码（单一叙事源）

实现与测试应对齐：

- `resolveDeliverable(task)` — 任务 → 交付类型（**任务文案**，不是 URL）
- `deliverablePlanMilestone(deliverable)` — 每 Run 一条 `PLAN: deliverable=…`
- `deliverablePreflightSkill(deliverable)` — 至多一个 preflight skill
- `DeliverableVerifyHook` — 交卷门槛

扩展阅读：`docs/PLAN.md` 阶段 A–E、`docs/MESSAGE_SYSTEM.md` 投影规则。

---

## 4. 与 Skill / Tool 的关系

| 层 | 职责 |
|----|------|
| **Tool** | 正交能力（observe / act / network / script_save …）；不增「某站专用 tool」 |
| **Skill** | L1 正文；由 **deliverable / intent** 决定 load 哪个，不在 skill 里写 host if |
| **Hook** | Verify、安全、重复观察熔断；**不**承载完整 Plan |
| **Plan** | deliverable 里程碑 + 模型协议（KERNEL）；新行为先改这里 |

---

## 5. 状态

| 日期 | 说明 |
|------|------|
| 2026-10-01 | 用户拍板：禁止 host 分支；新行为先写 deliverable Plan |
