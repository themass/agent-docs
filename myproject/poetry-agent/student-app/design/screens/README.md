# 界面截图（开发中的视觉反馈）

> **演示数据，占位素材。** 文字来自内容底座的草稿导出；图片、人物、声音是任务 C 的占位示意（`not_for_release`）。**都还没有发布，也不是史实。**

由 `student-app/frontend/scripts/shoot.mjs` 生成：无头 Chrome 对每个视图 × 设备截图，并审计 DOM（触控目标、横向溢出、对比度、图片是否加载、控制台错误、失败请求、隐私约束）。这是开发工具，不是测试套件，没有断言页面“对不对”，只报告“哪里看起来有问题”。重新生成：

```bash
node student-app/frontend/scripts/shoot.mjs            # 全部
node student-app/frontend/scripts/shoot.mjs --only=meet --vp=phone
```

设备：phone 390×844（2×，安全区上 47 下 34）、ipad-p 820×1180、ipad-l 1024×768。agent 为脚本模式，不调用任何模型网关。

| 文件 | 看什么 | <44px 目标 | 低对比文字 | 检查 |
|---|---|---|---|---|
| `01-home-first-run.phone.png` | 首次进入的数据说明；不记录前不产生任何事件 | 0 | 0 | 通过 |
| `01-home-first-run.ipad-p.png` | 首次进入的数据说明；不记录前不产生任何事件 | 0 | 0 | 通过 |
| `02-home.phone.png` | 一首诗当主角（接着上次），下面两个小门；家长入口在右上角；没有分数/打卡 | 0 | 0 | 通过 |
| `02-home.ipad-p.png` | 一首诗当主角（接着上次），下面两个小门；家长入口在右上角；没有分数/打卡 | 0 | 0 | 通过 |
| `02-home.ipad-l.png` | 一首诗当主角（接着上次），下面两个小门；家长入口在右上角；没有分数/打卡 | 0 | 0 | 通过 |
| `03-home-api-down.phone.png` | 接口全断时首页仍能用，两个入口还在 | 0 | 0 | 通过 |
| `04-timeline-find.phone.png` | 找诗：朝代/事件/作品；空白是虚线“还没有整理”；窄屏是列表 | 0 | 0 | 通过 |
| `04-timeline-find.ipad-p.png` | 找诗：朝代/事件/作品；空白是虚线“还没有整理”；窄屏是列表 | 0 | 0 | 通过 |
| `04-timeline-find.ipad-l.png` | 找诗：朝代/事件/作品；空白是虚线“还没有整理”；窄屏是列表 | 0 | 0 | 通过 |
| `05-timeline-find-selected.phone.png` | 选中《春望》：其余变淡、出摘要和“读这首诗” | 0 | 0 | 通过 |
| `05-timeline-find-selected.ipad-p.png` | 选中《春望》：其余变淡、出摘要和“读这首诗” | 0 | 0 | 通过 |
| `06-timeline-find-zoomout.ipad-p.png` | 缩小一级到“分期” | 0 | 0 | 通过 |
| `07-timeline-overview.phone.png` | 全貌：朝代层/诗人密度/主题线；未整理的是虚线 | 0 | 0 | 通过 |
| `07-timeline-overview.ipad-p.png` | 全貌：朝代层/诗人密度/主题线；未整理的是虚线 | 0 | 0 | 通过 |
| `07-timeline-overview.ipad-l.png` | 全貌：朝代层/诗人密度/主题线；未整理的是虚线 | 0 | 0 | 通过 |
| `08-timeline-overview-theme.phone.png` | 点主题线：高亮并列出成员 | 0 | 0 | 通过 |
| `08-timeline-overview-theme.ipad-p.png` | 点主题线：高亮并列出成员 | 0 | 0 | 通过 |
| `09-poem.phone.png` | 原文→进入那一年→注释→情境对照→出处→覆盖声明；两说并存 | 0 | 0 | 通过 |
| `09-poem.ipad-p.png` | 原文→进入那一年→注释→情境对照→出处→覆盖声明；两说并存 | 0 | 0 | 通过 |
| `09-poem.ipad-l.png` | 原文→进入那一年→注释→情境对照→出处→覆盖声明；两说并存 | 0 | 0 | 通过 |
| `10-poem-line-tapped.phone.png` | 点第 5 句出注释；点“↳ 对应”高亮句子 | 0 | 0 | 通过 |
| `10-poem-line-tapped.ipad-p.png` | 点第 5 句出注释；点“↳ 对应”高亮句子 | 0 | 0 | 通过 |
| `11-poem-api-down.phone.png` | 诗词页取不到时的说明 | 0 | 0 | 通过 |
| `12-lesson-read.phone.png` | 读：点一句出字词说明 | 0 | 0 | 通过 |
| `12-lesson-read.ipad-p.png` | 读：点一句出字词说明 | 0 | 0 | 通过 |
| `13-lesson-arrive-situation.phone.png` | 到：先一句处境（演绎标记）+「先看哪儿？」四个指路；四层先不展开 | 0 | 0 | 通过 |
| `13-lesson-arrive-situation.ipad-p.png` | 到：先一句处境（演绎标记）+「先看哪儿？」四个指路；四层先不展开 | 0 | 0 | 通过 |
| `13-lesson-arrive-situation.ipad-l.png` | 到：先一句处境（演绎标记）+「先看哪儿？」四个指路；四层先不展开 | 0 | 0 | 通过 |
| `14-lesson-arrive-ask.phone.png` | 到：自己问一句“他为什么被困在长安”，回答是带标记的气泡；问题只发给 /agent/v1/turn | 0 | 0 | 通过 |
| `14-lesson-arrive-ask.ipad-p.png` | 到：自己问一句“他为什么被困在长安”，回答是带标记的气泡；问题只发给 /agent/v1/turn | 0 | 0 | 通过 |
| `15-lesson-arrive-ask-uncovered.phone.png` | 到：问一句课里没讲的“杜甫后来当了宰相吗”，老实说没讲到，不猜 | 0 | 0 | 通过 |
| `16-lesson-arrive.phone.png` | 到：四层展开；视差场景、地图；“换个说法”的脚本回答 | 0 | 0 | 通过 |
| `16-lesson-arrive.ipad-p.png` | 到：四层展开；视差场景、地图；“换个说法”的脚本回答 | 0 | 0 | 通过 |
| `16-lesson-arrive.ipad-l.png` | 到：四层展开；视差场景、地图；“换个说法”的脚本回答 | 0 | 0 | 通过 |
| `17-lesson-arrive-narration.ipad-p.png` | “听”按钮 + 占位配音标记；真点击后请求了 m4a | 0 | 0 | 通过 |
| `18-lesson-arrive-audio-blocked.phone.png` | 自动播放被拦(非真实点击)：按钮旁出现“字幕”提示 | 0 | 0 | 通过 |
| `19-lesson-meet.phone.png` | 见：动画角色、角色扮演标记、演绎标记、“这是画师想象的” | 0 | 0 | 通过 |
| `19-lesson-meet.ipad-p.png` | 见：动画角色、角色扮演标记、演绎标记、“这是画师想象的” | 0 | 0 | 通过 |
| `19-lesson-meet.ipad-l.png` | 见：动画角色、角色扮演标记、演绎标记、“这是画师想象的” | 0 | 0 | 通过 |
| `20-lesson-return.phone.png` | 回：选第 5 句，出对应背景与脚本回答 | 0 | 0 | 通过 |
| `20-lesson-return.ipad-p.png` | 回：选第 5 句，出对应背景与脚本回答 | 0 | 0 | 通过 |
| `21-lesson-recite.phone.png` | 诵：示范、跟读、复述与补讲（只说缺哪一点，没有分数） | 0 | 0 | 通过 |
| `21-lesson-recite.ipad-p.png` | 诵：示范、跟读、复述与补讲（只说缺哪一点，没有分数） | 0 | 0 | 通过 |
| `21-lesson-recite.ipad-l.png` | 诵：示范、跟读、复述与补讲（只说缺哪一点，没有分数） | 0 | 0 | 通过 |
| `22-lesson-recite-audio.ipad-p.png` | 真点击“听一遍示范”后请求了示范 m4a | 0 | 0 | 通过 |
| `23-lesson-recite-consented.phone.png` | 同意后：事件与缺口上报，不含学生文字 | 0 | 0 | 通过 |
| `24-lesson-meet-media-off.phone.png` | 关闭图片与动画：名牌/文字，提示条 | 0 | 0 | 通过 |
| `24-lesson-meet-media-off.ipad-p.png` | 关闭图片与动画：名牌/文字，提示条 | 0 | 0 | 通过 |
| `25-lesson-meet-reduced-motion.phone.png` | 减少动效：换成静帧，不再有动画 | 0 | 0 | 通过 |
| `25-lesson-meet-reduced-motion.ipad-p.png` | 减少动效：换成静帧，不再有动画 | 0 | 0 | 通过 |
| `26-lesson-meet-weak-network.phone.png` | 弱网(数据节省)：静帧 | 0 | 0 | 通过 |
| `26-lesson-meet-weak-network.ipad-p.png` | 弱网(数据节省)：静帧 | 0 | 0 | 通过 |
| `27-lesson-meet-low-memory.phone.png` | 低内存：静帧 | 0 | 0 | 通过 |
| `28-lesson-meet-asset-missing.phone.png` | 角色清单 404：静帧→名牌的降级，台词文字仍在 | 0 | 0 | 通过 |
| `28-lesson-meet-asset-missing.ipad-p.png` | 角色清单 404：静帧→名牌的降级，台词文字仍在 | 0 | 0 | 通过 |
| `29-lesson-arrive-media-off.phone.png` | 关图：每层都是文字卡，没有“听”按钮 | 0 | 0 | 通过 |
| `29-lesson-arrive-media-off.ipad-p.png` | 关图：每层都是文字卡，没有“听”按钮 | 0 | 0 | 通过 |
| `30-lesson-arrive-reduced-motion.phone.png` | 减少动效：视差静止 | 0 | 0 | 通过 |
| `31-lesson-arrive-weak-network.phone.png` | 弱网：无配音按钮，字幕即台词 | 0 | 0 | 通过 |
| `31-lesson-arrive-weak-network.ipad-p.png` | 弱网：无配音按钮，字幕即台词 | 0 | 0 | 通过 |
| `32-lesson-arrive-asset-missing.phone.png` | 场景 404：“图没加载出来，文字不受影响” | 0 | 0 | 通过 |
| `32-lesson-arrive-asset-missing.ipad-p.png` | 场景 404：“图没加载出来，文字不受影响” | 0 | 0 | 通过 |
| `33-lesson-recite-media-off.phone.png` | 关图：没有示范音频，给出照着读的提示 | 0 | 0 | 通过 |
| `34-parent-gate.phone.png` | 家长闸门(防误触，不是验证) | 0 | 0 | 通过 |
| `34-parent-gate.ipad-p.png` | 家长闸门(防误触，不是验证) | 0 | 0 | 通过 |
| `35-parent-open.phone.png` | 数据说明与两个删除按钮；没有报表/付费 | 0 | 0 | 通过 |
| `35-parent-open.ipad-p.png` | 数据说明与两个删除按钮；没有报表/付费 | 0 | 0 | 通过 |
| `36-settings.phone.png` | 关图、拼音、字号 | 0 | 0 | 通过 |
| `36-settings.ipad-p.png` | 关图、拼音、字号 | 0 | 0 | 通过 |

“素材缺失”类截图由一个注入了 404 的开发服务器产生（只对 `a-dufu-bust`、`a-changan-dusk` 的入口文件返回 404，磁盘不动）。“弱网”用浏览器的数据节省信号（`navigator.connection.saveData`）模拟，“低内存”用 `deviceMemory=1` 模拟。
