下面整理一批 **英语学习** 和 **教学/知识学习类 Android 应用**。我把“可直接使用的学习 App”和“适合研究 Android 教学产品开发的项目”分开，避免把普通 UI Demo 误列成学习应用。

数据基于 GitHub API 当前快照，时间约为 **2026-10-12 UTC**。Stars 会变化，表中使用约数。

## 一、英语学习与语言学习类 Android 应用

GitHub 上真正专门做英语学习、且长期活跃的 Android 开源 App 数量不算多，比较成熟的方向主要集中在 **Anki 闪卡、词典、阅读查词、单词游戏和语言学习工具**。

| 项目 | 类型 | 技术栈 | Stars | 许可证 | 推荐理由 |
|---|---|---|---:|---|---|
| [ankidroid/Anki-Android](https://github.com/ankidroid/Anki-Android) | 闪卡记忆 | Kotlin | 约 12.0k | GNU AGPL-3.0 | Android 端 Anki 客户端，支持间隔重复、牌组、音频、图片和同步，适合背单词、短语和考试内容 |
| [yamin8000/freeDictionaryApp](https://github.com/yamin8000/freeDictionaryApp) | 英语词典 | Kotlin、Jetpack Compose | 约 220 | 未明确 | 使用 Free Dictionary API 和 Wiktionary API，适合查单词、音标、释义和例句 |
| [Konyaco/CollinsDictionary](https://github.com/Konyaco/CollinsDictionary) | 英语词典 | Kotlin Multiplatform | 约 170 | 需查看仓库 | Collins Dictionary 客户端，支持桌面端和 Android，适合研究跨平台词典应用 |
| [HuangAntimony/Hoshi-Reader-Android](https://github.com/HuangAntimony/Hoshi-Reader-Android) | 阅读查词 | Android、Yomitan、Anki | 约 435 | 需查看仓库 | 虽然主要面向日语学习，但“电子书阅读 + 即时查词 + Anki 制卡 + 有声朗读”的模式同样适合英语学习 |
| [obfusk/jiten](https://github.com/obfusk/jiten) | 词典工具 | Android、CLI、Web | 约 130 | 需查看仓库 | 主要是日语词典，但可参考本地词典、离线查询和多端复用设计 |
| [Livinglist/Manji](https://github.com/Livinglist/Manji) | 汉字 / 语言学习 | 移动端 | 约 170 | 需查看仓库 | 面向日语汉字学习，适合参考笔画、词汇、记忆进度和学习卡片设计 |
| [Carapacik/wordly-plus](https://github.com/Carapacik/wordly-plus) | 单词游戏 | Android | 约 120 | 需查看仓库 | 类似 Wordle 的猜词应用，适合用于英语词汇和拼写练习 |
| [Chimahon/chimahon](https://github.com/Chimahon/chimahon) | 沉浸式阅读 | Kotlin | 约 220 | GPL-3.0 | 支持词典查询、Anki 卡片挖掘和电子书阅读，虽然主要围绕日语，但非常适合研究语言学习工作流 |
| [NlptechProduct/Android-Keyboard](https://github.com/NlptechProduct/Android-Keyboard) | 输入法 / 词典 | Android、Java/Kotlin | 约 225 | 需查看仓库 | 支持大量词典、滑行输入和 AI 预测，对英语输入、拼写辅助和词汇联想有参考价值 |
| [tema6120/ForgetMeNot](https://github.com/tema6120/ForgetMeNot) | 闪卡学习 | Android | 约 440 | 需查看仓库 | 简单的 Android Flashcard 应用，适合快速建立单词记忆或学习卡片项目 |
| [azizkayumov/flashcard-maker-android](https://github.com/azizkayumov/flashcard-maker-android) | 闪卡制作 | Android | 约 60 | 需查看仓库 | 创建和导入电子闪卡，适合英语单词、短语和课程知识整理 |
| [kirill-markin/flashcards-open-source-app](https://github.com/kirill-markin/flashcards-open-source-app) | AI 闪卡 | 移动端、Web | 约 90 | 需查看仓库 | 面向考试、词汇和技术知识的 AI 闪卡应用，适合关注 AI 自动生成学习材料的方向 |

### 英语学习优先推荐

| 学习目标 | 推荐项目 |
|---|---|
| 背单词、记短语 | `AnkiDroid`、`ForgetMeNot` |
| 查英语词义和例句 | `freeDictionaryApp`、`CollinsDictionary` |
| 阅读中查词 | `Hoshi Reader`、`Chimahon` |
| 自动生成学习卡片 | `flashcards-open-source-app` |
| 英语拼写和词汇游戏 | `wordly-plus` |
| 英语输入和拼写辅助 | `Android-Keyboard` |

其中最值得优先体验的是 **AnkiDroid**。它不局限于英语，但从学习效果和生态成熟度来看，是这批项目里最可靠的学习工具之一。它的核心价值是间隔重复，而不是简单地把单词显示在卡片上。

## 二、离线知识与通用教学平台

| 项目 | 类型 | 技术栈 | Stars | 许可证 | 推荐理由 |
|---|---|---|---:|---|---|
| [kiwix/kiwix-android](https://github.com/kiwix/kiwix-android) | 离线百科 / 教材 | Kotlin | 约 1.5k | GPL-3.0 | 在 Android 上离线阅读 Wikipedia、课程资料和其他 ZIM 内容，适合没有稳定网络的学习场景 |
| [learningequality/kolibri](https://github.com/learningequality/kolibri) | 离线教育平台 | Python、Android/Web | 约 1.1k | MIT | 面向普惠教育的离线学习平台，可部署课程、视频、练习和学习进度 |
| [oppia/oppia-android](https://github.com/oppia/oppia-android) | 互动课程平台 | Kotlin | 约 420 | Apache-2.0 | 支持在线和离线学习，强调互动课程、练习和低网络环境下的教育访问 |
| [moodlehq/moodleapp](https://github.com/moodlehq/moodleapp) | LMS 学习管理系统 | TypeScript、Ionic | 约 1.0k | GPL-3.0 | Moodle 官方移动端应用，支持课程、作业、测验、通知和学习进度 |
| [openedx-unsupported/edx-app-android](https://github.com/openedx-unsupported/edx-app-android) | 在线课程平台 | Android | 约 300 | 需查看仓库 | Open edX 的 Android 客户端方向，适合研究课程、视频和学习进度整合 |
| [vishal2376/git-coach](https://github.com/vishal2376/git-coach) | 编程教学 | Android | 约 260 | 需查看仓库 | 面向 Git 学习的无广告教育应用，通过命令解释和练习帮助用户学习 Git |
| [SimonSchubert/Braincup](https://github.com/SimonSchubert/Braincup) | 记忆 / 专注 / 数学训练 | Android | 约 325 | 需查看仓库 | 结合记忆训练、专注练习和数学训练，适合作为轻量学习工具参考 |
| [Hash-Studios/e-learning-app](https://github.com/Hash-Studios/e-learning-app) | 在线课程 App | Flutter、Dart | 约 350 | 需查看仓库 | 开源教育应用，适合研究课程列表、视频学习、用户进度和 Flutter 移动端实现 |
| [fireship-io/flutter-firebase-quizapp-course](https://github.com/fireship-io/flutter-firebase-quizapp-course) | 测验教学项目 | Flutter、Firebase | 约 590 | 需查看仓库 | 用 Quiz App 展示 Firebase 和 Flutter，适合学习者做教学项目练习 |
| [processing/processing-android](https://github.com/processing/processing-android) | 编程教育 / 创意编码 | Java、Android | 约 800 | LGPL-2.1 | 将 Processing 带到 Android，适合用图形、动画和交互方式学习编程 |
| [ob-f/OpenBot](https://github.com/ob-f/OpenBot) | 机器人教育 | Android、Python、C++ | 约 3.5k | 需查看仓库 | 使用 Android 手机作为机器人“大脑”，适合机器人、计算机视觉和移动端硬件教学 |
| [YangDai2003/OpenNote-Compose](https://github.com/YangDai2003/OpenNote-Compose) | 学习笔记 | Kotlin、Jetpack Compose | 约 780 | 需查看仓库 | Markdown 笔记应用，适合做个人知识库、课程笔记和学习资料整理 |
| [koreader/koreader](https://github.com/koreader/koreader) | 电子书阅读 | Lua、Android | 约 30.3k | AGPL-3.0 | 支持 PDF、EPUB、DjVu 等格式，适合长期阅读教材、技术书和语言学习材料 |

## 三、适合学习 Android 开发的教学型项目

下面这些项目不一定是“教学内容 App”，但很适合用来学习 Android 应用开发。它们通常有完整页面、数据流、持久化、网络请求或现代 UI，参考价值比单独的控件 Demo 更高。

| 项目 | 学习主题 | 技术栈 | Stars | 推荐学习内容 |
|---|---|---|---:|---|
| [android/nowinandroid](https://github.com/android/nowinandroid) | 官方现代架构 | Kotlin、Jetpack Compose | 约 21.9k | 单向数据流、Offline-first、模块化、Room、Paging、依赖注入和测试 |
| [android/compose-samples](https://github.com/android/compose-samples) | Compose UI | Kotlin、Jetpack Compose | 约 23.5k | Compose 页面、状态管理、导航、Material 3 和响应式布局 |
| [android/architecture-samples](https://github.com/android/architecture-samples) | 架构模式 | Kotlin、AndroidX | 约 45.9k | MVVM、Repository、状态管理和不同架构方案对比 |
| [GetStream/whatsApp-clone-compose](https://github.com/GetStream/whatsApp-clone-compose) | 即时通信 App | Kotlin、Compose | 约 1.4k | 聊天列表、消息页面、实时通信和媒体消息 |
| [EranBoudjnah/CleanArchitectureForAndroid](https://github.com/EranBoudjnah/CleanArchitectureForAndroid) | Clean Architecture | Kotlin、Compose、Hilt | 约 840 | 多模块、MVVM、依赖注入、协程和测试 |
| [miaowmiaow/fragmject](https://github.com/miaowmiaow/fragmject) | Android 入门项目 | Kotlin、Compose、Room | 约 1.5k | 日历、数据库、WebView、页面组织和实际业务代码 |
| [joreilly/Confetti](https://github.com/joreilly/Confetti) | Kotlin Multiplatform | Kotlin、Compose、GraphQL | 约 1.1k | Android、iOS、桌面、Web 多端共享代码和 GraphQL |
| [joreilly/BikeShare](https://github.com/joreilly/BikeShare) | KMP 实战 | Kotlin、Compose、SwiftUI | 约 830 | 网络请求、Room、本地持久化、跨平台 UI 和 MVVM |
| [prof18/feed-flow](https://github.com/prof18/feed-flow) | RSS 学习项目 | Kotlin Multiplatform、Compose、SwiftUI | 约 1.3k | Android/iOS/桌面端共享业务逻辑和离线内容 |
| [YangDai2003/OpenNote-Compose](https://github.com/YangDai2003/OpenNote-Compose) | 笔记应用 | Kotlin、Jetpack Compose | 约 780 | Markdown 编辑器、文件管理、状态管理和本地数据 |
| [hushenghao/AndroidEasterEggs](https://github.com/hushenghao/AndroidEasterEggs) | Compose 综合练习 | Kotlin、Room、Hilt | 约 1.3k | Material You、动态颜色、数据库和多个 UI 组件 |
| [googlemaps/android-maps-compose](https://github.com/googlemaps/android-maps-compose) | 地图开发 | Kotlin、Jetpack Compose | 约 1.3k | 在 Compose 中集成 Google Maps SDK、标记、状态和交互 |

## 四、如果要做“英语学习 Android 应用”，推荐参考组合

可以按下面的方式组合项目能力：

```text
AnkiDroid
  └─ 间隔重复、牌组、复习计划

freeDictionaryApp / CollinsDictionary
  └─ 词典、释义、音标、例句

Hoshi Reader / Chimahon
  └─ 阅读、划词查词、Anki 卡片挖掘

AntennaPod / NewPipe
  └─ 音频、视频、后台播放、字幕与学习内容

Now in Android / Compose Samples
  └─ Compose、Room、网络请求、离线优先和现代架构
```

一个完整的英语学习 App 可以设计成：

- 单词和短语卡片；
  阅读时划词查词，并把例句加入复习卡片；
- 听力材料支持变速、循环播放和进度保存；
- 跟读录音，方便对比原声；
- 按间隔重复安排每日复习；
- 下载教材和音频，支持离线学习；
- 用 AI 生成场景对话、解释语法和提供练习反馈。

以上是产品设计建议，具体能力需要分别实现，不能认为前面每个项目都已包含这些功能。

补充几处筛选边界，方便你选项目：

| 项目或方向 | 应如何理解 |
|---|---|
| **AnkiDroid** | 优先推荐的通用记忆工具，可用于英语，也可用于其他学科；学习内容取决于牌组 |
| **freeDictionaryApp** | 英语词典候选，依赖外部词典 API；本轮尚未核实其安装包与许可证全文 |
| **CollinsDictionary** | 跨平台词典参考项目；查到的最近推送为 2024-04-30，使用前需确认接口是否仍可用 |
| **Hoshi Reader、Chimahon、Jiten、Manji** | 主要面向日语，应放在“语言学习参考”栏，不应当作英语专用 App 推荐 |
| **Moodle App** | 适合课程、作业和测验管理，需要连接相应的 Moodle 站点 |
| **Kolibri** | 离线教育平台；前面查的是平台主仓库，Android 安装与部署方式还需单独核实 |
| **旧 Open edX Android 仓库** | 位于 `openedx-unsupported` 组织下，建议作为历史架构参考，暂不列为首选安装应用 |
| **Flutter Quiz / E-learning 示例** | 更适合开发教学与原型参考，不代表已有完整课程内容或可直接部署的教学平台 |

另外，前面部分许可证是未经本轮核验的补充信息，**应以各仓库的 LICENSE 文件为准**；最近推送时间也只能说明仓库发生过更新，不能直接证明应用全部功能可用。

按你的用途，我建议先看这六个：**英语记忆选 AnkiDroid，英语查词看 freeDictionaryApp，离线知识阅读选 Kiwix，学校课程管理看 Moodle App，互动教学看 Oppia Android，教材阅读选 KOReader。** 这组覆盖了记忆、查词、阅读、课程和练习，比较适合继续做应用体验与内容选题。