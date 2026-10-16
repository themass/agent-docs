# SayAgain Android 首发能力地图 v0.1

> 状态：待产品确认。本文只确定首发能力边界、依赖方向和建设顺序，不代表已经开始编码。
> 日期：2026-10-13

## 当前有效决策

- 产品形态：Android 英语学习 App。
- 首发核心：单词 + 固定搭配。
- 数字人：作为学习引导、示范和反馈角色，不是独立聊天功能。
- 长期方向：逐步扩展句子、语法、听力、口语、阅读、写作和综合任务。
- 旧的“英语跟读纠错”设计：保留为历史探索，不作为本首发的功能边界。

## 能力模块

| 模块 ID | 责任 | 依赖 | 首发状态 |
|---|---|---|---|
| content-model | 单词、词义、固定搭配、例句和媒体内容模型 | — | P0 |
| lesson-session | 今日计划、新学流程、学习进度和退出恢复 | content-model | P0 |
| practice-engine | 识别、回忆、图片/音频、搭配补全等练习 | content-model, lesson-session | P0 |
| review-scheduler | 当日重试、跨日复习、复习队列和掌握状态 | content-model, practice-engine | P0 |
| digital-coach | 数字人出场、动作、语音、提示和反馈 | content-model, lesson-session | P0（轻量） |
| library-progress | 词包、词条详情、学习记录和薄弱项 | content-model, review-scheduler | P1 |
| content-delivery | 内容版本、下载、离线和素材完整性 | content-model | P1 |
| account-commerce | 登录、同步、订阅和付费 | library-progress, content-delivery | P2 |
| future-language-skills | 句型、语法、听说读写综合能力 | content-model, practice-engine | 后续 |

## 建设顺序

1. content-model
2. lesson-session + practice-engine
3. review-scheduler
4. digital-coach
5. library-progress
6. content-delivery
7. account-commerce
8. future-language-skills

## 边界原则

- 每个模块必须能说明它检验或支持哪一种学习能力。
- 玩法不能反过来决定课程内容。
- P0 不做自由聊天、完整口语评分、社交排行榜、复杂 Cocos 游戏和大规模 AI 自动生成题库。
- 如果目标市场、用户年龄、首发语言或商业模式变化，先更新能力地图和 PRD，再改变实现计划。
