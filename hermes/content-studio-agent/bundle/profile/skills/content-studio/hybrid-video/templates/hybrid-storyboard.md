# Hybrid 视频分镜：{主题} | {YYYY-MM-DD}

## 视频目标

- **链路**: hybrid-video（第三条独立链路，不替代 sop/mpt）
- **核心 thesis**: {一句行业判断}
- **目标时长**: {seconds}
- **AI 素材策略**: 仅 2-3 段 `ai_broll`，其余用 GitHub 证据和概念卡

## 入选项目

| 顺序 | 排名 | 项目 | 链上角色 | 证据画面 |
|------|------|------|----------|----------|
| 1 | #{rank} | owner/repo | {role} | github_scroll_callout |
| 2 | #{rank} | owner/repo | {role} | github_scroll_callout |
| 3 | #{rank} | owner/repo | {role} | github_scroll_callout |

## 分镜表

| 段ID | 时长 | asset_type | visual_type | 素材/Prompt | 目的 |
|------|------|------------|-------------|-------------|------|
| intro-thesis | 10-12s | card | concept_card | thesis + 证据 | 建立判断 |
| intro-ai-broll | 5-7s | ai_broll | ai_generated | English visual_prompt | 把抽象趋势视觉化 |
| project-1-github | 18-22s | github | github_scroll_callout | owner/repo | 展示真实证据 |
| project-1-card | 6-8s | card | concept_card | 痛点/能力/意义 | 解释项目角色 |
| project-2-github | 18-22s | github | github_scroll_callout | owner/repo | 展示真实证据 |
| project-2-card | 6-8s | card | concept_card | 痛点/能力/意义 | 解释项目角色 |
| project-3-github | 18-22s | github | github_scroll_callout | owner/repo | 展示真实证据 |
| project-3-card | 6-8s | card | concept_card | 痛点/能力/意义 | 解释项目角色 |
| outro-summary | 10-12s | card | summary_card | 长期判断 | 收束观点 |

## AI Visual Prompts

### intro-ai-broll

```text
{English prompt, no fake text, no logos, no generic coding stock footage}
```

## 风险与降级

- Seedance 未配置：`ai_broll` 降级为 fallback concept card。
- GitHub 段失败：保留占位或中止，不能替换成泛素材。
- 当前 sop/mpt 产物不受影响。
