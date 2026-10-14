# 百词斩 APK 静态研究报告 v0.1

> 研究对象：`/Users/gqli/work/android/app/baicizhan.apk`  
> 版本：`7.10.22`（versionCode `7102202`）  
> 包名：`com.jiongji.andriod.card`  
> SHA-256：`74082eb083622c9a2408743584868031d52ab351c89c23c1d54e16dabea65a8e`  
> 研究日期：2026-10-13

## 1. 研究边界

本报告只记录已经得到的**静态 APK 证据**：ZIP/资源结构、DEX 类/字段/方法元数据和内置 JSON 数据结构。没有执行 APK，也没有安装、登录、联网或操作 UI。因此，下面的“存在”表示包内存在，不表示用户运行时一定会看到或按此顺序使用。

目前缺少 `jadx-headless-mcp 0.7.1`，所以暂未完成 Java/Kotlin 方法级反编译。题型顺序、答错处理、服务端复习调度和付费边界不能从本报告直接确定。

## 2. 包和内容结构

- APK 约 406 MiB，包含 13 个 DEX，ZIP 中约 7,166 个成员。
- `minSdkVersion=24`，`targetSdkVersion=34`。
- 包内存在 `assets/GameHost/` 游戏宿主及一个 Cocos Creator 句子游戏：
  - `gameId=bcz_cocos_sentence`
  - 版本 `0.0.18`
  - Cocos Creator `3.8.7`
  - Android 目标平台
- 包内存在多组 Spine/Lottie 角色与答题反馈资源，静态路径中可见 Penguin、Cat、Rabbit、Raccoon、Robot 等角色命名。

### 对产品的启发

百词斩不是把“单词卡片”作为唯一界面，而是把内容、题型、角色反馈和独立游戏包组织成多个体验层。SayAgain 可以借鉴“内容对象与体验容器分离”的结构，但首发不应复制大型游戏宿主：首发只需要一个稳定的词汇学习闭环和少量数字人动作。

## 3. 固定搭配是独立内容对象

包内的 `assets/phrasetraining/` 有三类结构化文件：

- `packed_short_phrase.json`：422 条固定搭配记录。
- `get_all_short_phrase_groups.json`：59 个分组；每组 4、5 或 8 条，合计 422 个搭配条目。
- `get_short_phrase_topics_by_group.json`：59 组练习配置，共 2,132 条配置行。

单条搭配静态字段包括：

- `topic_id`、`word`
- `mean_cn`
- `word_image`、`word_audio`
- `sentence`、`sentence_trans`、`sentence_audio`
- `sentence_word_highlight`
- `sentence2`、`sentencen2_trans`、`sentence2_audio`
- `sentence2_word_highlight`
- `similar_highlight`
- `exam_info`
- `img_option`

示例对象是 `cut out`，带有中文释义、图片路径、词音频、主例句、译文、例句音频、重点高亮和第二条例句。这个结构支持“表达块 + 语境 + 复现”的学习，而不是把短语当成单词详情页底部的一行文本。

### 对 SayAgain 的直接结论

SayAgain 的固定搭配应建模为独立对象：

```text
PhraseItem
- expression
- category: collocation | phrasal_verb | idiom
- meanings[]
- pronunciation/audio
- scene/image or digital-human action
- primary_example
- example_translation
- example_audio
- highlighted_span
- variant_examples[]
- related_items[]
- learning_state
- review_state
```

但不能复制百词斩的题库、图片、音频、命名、角色或实现。我们借鉴的是信息结构和教学问题，不是素材。

## 4. 练习配置表现出多种题型方向

`get_short_phrase_topics_by_group.json` 中出现多个 `type_hint`，具体数值对应的 UI 语义尚未通过方法反编译确认，但配置内容本身显示了这些方向：

- 图片选项。
- 中文释义选项。
- 关联搭配/同组干扰项。
- 以若干 `topic_id` 组成的选择或复习配置。
- 一组“示例/是否执行”的控制字段 `is_do_example`。

DEX 元数据中的题型枚举还出现了英文到中文、中文到英文、听音到单词、句子到中文、完整拼写、部分拼写、情境题、图片题、押韵题、深度题、录音判断等命名方向。

### 证据等级

这些名称证明“代码或资源为这些题型保留了模型/枚举”，不能证明所有题型在 7.10.22 的每个词包都会被触发，也不能证明顺序和评分规则。

## 5. 学习记录与复习模型线索

`TopicLearnRecord` 静态字段包括：

- 做题次数：`doNum`
- 错误次数：`errNum`
- 最近操作时间：`lastDoTime`
- 复习轮次：`reviewRound`
- 主题分数：`topicScore`
- 累计用时：`totalTime`
- 是否今日新内容：`isTodayNew`
- 题目、日期、同步和媒体状态字段

`ScheduleRecord` 静态字段包括：

- `dailyCount`、`reviewCount`
- `finishedCount`
- `lastDakaTime`
- `todayMaxCombo`
- 词书选择与同步版本字段

`ReviewMode` 出现 `BROWSE`、`RECALL`、`SPEED` 三种值。

### 对 SayAgain 的建议

首发先保留三种清晰学习状态，而不是把每种题型都做成独立入口：

1. **看懂**：首次接触、图像/数字人/音频/释义。
2. **想起**：隐藏答案后主动回忆。
3. **巩固**：在变式、搭配和到期复习中再次提取。

建议内部记录“内容 × 方向 × 结果”，至少区分：

- 看到英文能否理解；
- 看到含义/情境能否想起英文；
- 听到声音能否识别；
- 能否在固定搭配中补出表达。

不要把一次浏览、看答案后的“答对”或连击数直接当成掌握。首发也不应宣称已经复刻百词斩或 FSRS 的真实调度算法。

## 6. 角色与反馈资源

静态资源中有角色动画和答题反馈动画。这说明角色可能被用于引导、反馈或内容包装，但仅凭资源命名不能确认实际出现时机。

SayAgain 首发建议把数字人限制在三个高价值节点：

- **引入**：用动作和场景解释具体词或搭配；例如 `wash your hands` 时指向手部。
- **示范**：播放发音、做一个可理解的动作或情境演示。
- **反馈**：答错时给一条短提示，答对时给简短鼓励。

数字人不应在每道题都讲话，否则会增加等待和认知负担。数字人动作必须服务于当前词义，抽象词应使用情境、对比和例句，不强行做“指物”。

## 7. “采用 / 改造 / 舍弃”

| 百词斩静态线索 | SayAgain 采用 | 改造 | 首发舍弃/暂缓 |
|---|---|---|---|
| 固定搭配独立数据与分组 | 表达块作为独立内容对象 | 每条搭配用明确教学目标和真实语境 | 大规模考试标签体系 |
| 图片、音频、例句、重点高亮 | 多模态首次学习 | 图片可由数字人情境替代或补充；素材全部自制/授权 | 直接复用原图音频 |
| 多种方向题型 | 识别→回忆→搭配补全 | 每题标注验证能力，按状态调度 | 押韵、深度、速度等复杂题型 |
| BROWSE/RECALL/SPEED 线索 | 看懂/想起/巩固三层状态 | 先做短时主动提取，再做到期复习 | 首发不做强速度压力 |
| 连击、最大连击字段 | 可做轻量反馈 | 不让连击代表掌握度 | 排行榜、重社交竞争 |
| Cocos 句子游戏包 | 长期保留“句子任务”方向 | 与词汇掌握有明确迁移关系时再做 | 不纳入词汇首发核心闭环 |

## 8. 当前未解问题

- 真实学习流程的页面顺序和题型触发条件。
- `type_hint` 数值与具体交互的映射。
- 答错、提示、跳过、退出恢复的规则。
- 复习时间表和服务端调度算法。
- 固定搭配训练是否与主单词状态共享。
- Cocos 句子游戏在整个产品中的入口、奖励或独立课程角色。
- 角色动画是否用于教学还是仅用于反馈/营销。

这些问题需要方法级反编译或在授权设备/模拟器上的运行观察才能回答。

## 9. 下一步研究顺序

1. 如果提供 JADX 组件，先反编译 `Phrase`、题型枚举、短语训练 Activity/ViewModel、学习记录和复习调度相关类。
2. 如果提供授权 Android 设备/模拟器，优先观察：新词引入、固定搭配入口、题型顺序、提示/答错、退出恢复、复习到期。
3. 将观察结果转成 SayAgain 的独立 PRD：内容对象、题型矩阵、状态机、数字人时机和 v0.1 样板词包。
4. 对竞品只记录“教学问题与交互模式”，不复制代码、题库、素材、角色或品牌。

## 10. 证据与可追溯性

- REA 归档检查 Evidence ID：`ev_683f27eb7faba3a128281f7cd660a1076f119aa92015a8a12153316782d7e515`。
- REA 归档清单 Evidence ID：`ev_8187d5d9002947ddfdb1f0cca4fecdf4405a571465565228f66c83743d15cb93`。
- 完整归档证据：`/Users/gqli/work/deepagents/docs/myproject/sayagain/baicizhan-evidence.json`。REA 清单只能支持包内路径、大小、摘要等归档事实，不能支持教学语义。
- Manifest/JSON/DEX 元数据解释来自本目录中的只读分析脚本及 JSON 输出，属于本地结构解析结果，不冒充 REA 方法反编译证据。
- `phrase-structure-summary.json` 保存本轮搭配分组与练习配置统计；原始教学素材未复制进产品目录。
- 包内部分搭配资源引用了较早的年份和素材路径；这些数据的存在不证明它们是当前主入口使用的最新课程，也不代表竞品全量在线题库。
