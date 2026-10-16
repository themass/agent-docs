---
type: research
status: review
version: v0.1
date: 2026-10-15
source_of_truth: false
---

# SayAgain 教学方法论研究与开源参考 v0.1

日期：2026-10-13。状态：第一轮公开资料核验与产品适配建议。
研究范围：官方教学资源、研究作者资料、官方 GitHub README；未运行项目、未完成源码审计、未验证本产品效果。不是“全球最佳教学法”排名。

## 1. 结论

没有在本轮找到一个可直接替代我们完整设计的“亲子小学英语 + 3D 伙伴 + 可扩展课程 + PK”开源教学体系。
建议分层组合，而不是找一个 App 克隆：

- 能力参照：Cambridge Young Learners 的 Pre-A1 / A1 / A2 资源与任务；
- 长期课程平衡：Paul Nation Four Strands；
- 首发身体主题：TPR（全身反应法）与动作/语义联系；
- 学习保持：提取练习与间隔复习；
- 亲子延伸：示范、轮流互动、简单可理解任务；
- 工程参考：AnkiDroid / FSRS / H5P / Kolibri，分别借鉴不同部分。

不能混淆：能力框架不是教材；教学方法不是算法；开源系统不是教学效果证据；免费可访问的资料不等于可以复制进商业 App。

## 2. 方法论参照与适配

### 2.1 Four Strands：防止产品变成纯刷词系统

Paul Nation 的作者原文将课程机会分为：意义导向输入、意义导向输出、语言形式学习、流利度发展，建议完整课程大致平衡四类机会。

产品适配建议：

| 类别 | 我们的活动 | 缺失风险 |
|---|---|---|
| 意义导向输入 | 听懂小故事、指令、情境 | 只听孤立单词，听不懂句子 |
| 意义导向输出 | 向家长描述、请求、回答 | 只做选择题，无法表达 |
| 语言形式学习 | 词义、发音、词形、搭配、后续语法 | 缺少准确性与语言知识 |
| 流利度发展 | 熟悉内容重复使用、顺畅完成已知任务 | 永远只学新东西，不会熟练用 |

不要把比例机械变为“每节五分钟正好四等分”；首发是受限词汇产品，不是完整四技能课程。流利度也不等于 PK 手速。需在单元或课程尺度检查机会分布，并注明尚未覆盖的部分。

作者原文：
https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/paul-nations-publications/publications/documents/2007-Four-strands.pdf

### 2.2 TPR：身体主题的局部方法，不是全产品唯一方法

British Council 的 TPR 教学指南将语言与身体动作结合；教师示范后，学生通过动作回应，适合动作词、身体部位等内容。

我们的序列建议：听指令 → 观察角色示范 → 跟做 → 撤掉示范理解指令 → 亲子轮流发指令。

边界：屏幕点选证明选择，不证明孩子真的做了动作；不能覆盖所有抽象词、阅读、写作；为无法或不愿做某动作的孩子提供点图替代。3D 是呈现载体，不能据此宣称比普通示范更有效。

官方实践资源：
https://www.teachingenglish.org.uk/professional-development/teachers/managing-lesson/total-physical-response-tpr

### 2.3 提取与间隔复习：支持保持，不替代理解与应用

IES/WWC 指南包含间隔学习、图文结合、具体与抽象连接、利用测验促进学习等建议，并分别标示证据等级。

产品规则：先提供可理解示范，再在答案隐藏条件下尝试提取；提示/揭示后完成与无提示完成分开；复习跨日且换题面；不要把固定 1/3/7 日写成最优科学公式。实际节奏需试学调优。

官方指南：
https://ies.ed.gov/ncee/wwc/PracticeGuide/1

### 2.4 儿童能力参照：不把词表等同等级

Cambridge 儿童资源以 Pre-A1 Starters、A1 Movers、A2 Flyers 提供阶梯式参照，配有教师手册、词表、图片、活动与任务材料。

建议研究目标描述与任务复杂度：从指认、听懂短指令，到熟悉场景问答、句子连接。不要因学完一组词就宣称 A1 达标，也不要照搬考试题库或受保护素材。

https://www.cambridgeenglish.org/exams-and-tests/qualifications/young-learners/paper/
https://www.cambridgeenglish.org/exams-and-tests/flyers/preparation/

### 2.5 亲子语言互动：真实使用，而非家长代答

EEF 的口语干预资料涉及成人示范、支架、反馈和有目的的互动；Cambridge 亲子绘画活动给出描述/猜图、角色互换、孩子制作闪卡等实践。

建议每个单元配置一个不依赖家长英语水平的短任务：App 播音 → 孩子指认；轮换发指令；用家庭物品找目标。观察参与与语言使用，家长自报与客观作答分开。

证据边界：EEF 学校口语干预结果不能直接当作中文家庭英语 App 的效果量。

https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/oral-language-interventions
https://www.cambridgeenglish.org/learning-english/parents-and-children/your-childs-interests/learn-english-through-drawing/

## 3. GitHub 项目：参考什么，不参考什么

| 项目/官方仓库 | 已核验定位 | 建议研究 | 不应直接照搬 |
|---|---|---|---|
| AnkiDroid | Android 闪卡项目 | 媒体卡片、复习交互与内容/卡片分离的实现 | 儿童 UI、完整课程、自动把自评当客观能力 |
| FSRS4Anki | 间隔复习调度与参数优化 | 复习历史、调度/优化分离、后续算法候选 | 用时直接映射掌握；未经校准的儿童混合活动评级 |
| H5P Interactive Book | 互动内容书项目 | 可组合活动、内容配置与展示逻辑分离 | 作为原生 3D 客户端或完整教学法 |
| Kolibri | 离线教育学习平台 | 离线内容分发、课程资源组织的后续研究 | 直接采用整个平台作为移动产品架构 |

官方仓库：
- https://github.com/ankidroid/Anki-Android
- https://github.com/open-spaced-repetition/fsrs4anki
- https://github.com/h5p/h5p-interactive-book
- https://github.com/learningequality/kolibri

只核验项目定位，不宣称源码已评估、原生兼容已验证或适合直接集成。采用代码前另做模块许可、依赖、维护、体积与性能评估；卡片素材和课程内容许可单独检查。

## 4. 对原有框架的修订建议

1. “五环主题学习”保留为课内编排，不称独立实证教学流派。
2. 加入 Four Strands 的课程级机会检查，避免听说读写成为空口号。
3. 将 TPR 标记为适用身体/动作主题的方法，不强行用于所有主题。
4. 单元不仅罗列词：先明确一个可理解的情境任务与能力条件。
5. 复习算法位于教学证据规则之后；多选正确不能直接等同自由回忆评级。
6. 数字人与 PK 都是可替换形式；必须与更简单的画面/个体练习比较。
7. 亲子任务须家长不会英语也能完成，孩子独学路径不能依赖家长全程在场。

## 5. 下一轮完善方法论的具体交付

在修改原型/选型之前，先完成：

- 教学原则决策表：每项原则的来源、适用范围、产品规则、验证方式；
- 课程机会矩阵：每个单元输入/输出/形式学习/熟练使用的活动分布；
- 内容选择规则：必要性、复用性、难度、搭配、词义、可具象性，不仅按主题凑词；
- 支架与证据矩阵：提示等级、客观/观察/自评证据、补救与复习方向；
- 《我的脸》与第二个不同主题的小样：检验框架是否真正可复用；
- 家庭试学计划：当日理解、跨日保持、新图迁移、家长负担、孩子意愿；
- 外部英语教研审阅：内容与目标适龄性不能只由代码和 AI 推断。

研究阶段先查文档与教学结构，不下载或安装这几个项目，也不提前锁定技术方案。
