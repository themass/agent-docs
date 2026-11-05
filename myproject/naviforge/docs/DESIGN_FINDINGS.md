# NaviForge 设计问题与优化路线

核对与落地：2026-11-05 → 2026-11-06。

- 评审底稿：[`BEST_PRACTICES_REVIEW.md`](BEST_PRACTICES_REVIEW.md)、[`PROMPT_SKILL_TOOL_DESIGN_REVIEW.md`](PROMPT_SKILL_TOOL_DESIGN_REVIEW.md)、[`HOOK_SKILL_POLICY_ARCHITECTURE_DEEP_REVIEW.md`](HOOK_SKILL_POLICY_ARCHITECTURE_DEEP_REVIEW.md)
- 广告：[`store-assets/ads/AD_SLOTS.md`](store-assets/ads/AD_SLOTS.md)

骨架保持不变：极简 Kernel、L1/L2/L3 skill、grouped-verb tools、first-wins hooks。不要再往 Kernel 堆站点 playbook。

## 已落地

| 项 | 现状 |
|----|------|
| Hook 顺序 / Network 状态机 / Page State 媒体优先 | 见前序改动 |
| 共享 task signals + soft 路由加权 | `task-signals.ts`、`preferredSkillIdsForTask` → `routeSkills` |
| replan 接线 | ActionLoop / Dedupe 只 skip + `replanRequired`；`NoProgressHook` 仍硬停 |
| ToolSpec meta | `packages/shared/src/tool-specs.ts`（risk/usage）；`tools[]` description 经 `formatToolApiDescription`；参数 SSOT 为 `TOOL_PARAMETERS` |
| Skill 硬门槛 | `enforceSkillToolAllowlist` 时用 **enabled skills ∪ SAFE_BASE**，不用 `routeSkills` 单独锁工具；host 路径不再从单次路由收窄 `allowedTools` |
| harvest 拆分 | L1：`media-harvest` / `form-harvest` / `price-harvest`；`harvest` 等为 alias |
| 条件 P-SPAWN | KERNEL 只留短提示；`composeSystemPrompt({ includeSpawn })` + `shouldIncludeSpawnSection(task)` |
| note 预算 | `WORKING_SET.maxPinnedNotes` + `capPinnedConstraintNotes` |
| 文档 | `OPTIMIZATION_PLAN` catalog **13** |

## 仍可观察

| 项 | 说明 |
|----|------|
| NoProgress 是否误杀 | replan 软跳过后若仍无进展才硬停；看 corpus / 实机 |
| ToolSpec 再收紧 | 把 `TOOL_PARAMETERS` 与 catalog 完全合并成单一 `ToolSpec[]` 数组（当前 meta + parameters 分文件） |
| 生成目录 | 改 catalog 后可跑 `scripts/export-prompt-tool-skill-doc.ts` 刷新 `AGENT_PROMPT_TOOL_SKILL_CATALOG.md` |
