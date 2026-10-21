---
name: jobcome-seo
description: >-
  JobCome（舟卡）站点 SEO：中文关键词、百度+Google 双引擎注意事项、与 claude-seo 技能配合。
  在改 metadata、sitemap、落地页文案或做 SEO 审计时使用。
---

# JobCome / 舟卡 SEO

## 引擎支持

| 引擎 | claude-seo 侧重 | 本项目已做 |
|------|-----------------|------------|
| **Google** | 主战场：CWV、Schema、E-E-A-T、GEO | metadataBase、OG、JSON-LD、sitemap、robots |
| **百度** | 通用技术 SEO 仍适用 | 中文 meta、keywords、Baiduspider、host+sitemap |

上线后在百度搜索资源平台与 Google Search Console 提交 sitemap，并设置 `NEXT_PUBLIC_SITE_URL`。

## 关键词

简历优化、AI简历、简历解析、模拟面试、岗位匹配、JD匹配、求职、舟卡、JobCome — 见 `frontend/web/lib/seo/site.ts`。

## claude-seo

已安装：`~/.cursor/skills/seo` 及 25 个子技能。脚本：`~/.cursor/skills/seo/scripts/claude-seo`。
