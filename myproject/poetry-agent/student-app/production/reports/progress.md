# 素材生产进度

生成时间:2026-11-07T03:20:16.643Z(由 `node tools/prod.mjs report` 生成,勿手改)

## 春望(杜甫)

共 28 个任务。

状态:TODO 28

- 已有正式素材:**0**
- 仅有占位(不可上线):**26**
- 既无正式也无占位(前端走降级):**0**
- 暂不可派发(依据未定):**10**

| 优先级 | 任务 | 等级 | 状态 | 素材现状 | 暂不可派发 |
|---|---|---|---|---|---|
| P0 | `a-chang-an-map-text` 长安示意地图(文字卡) | L0 | TODO | 占位 |  |
| P0 | `a-changan-dusk` 春日长安(视差场景) | L1 | TODO | 占位 | ⚠ scene_spec |
| P0 | `a-changan-dusk-text` 春日长安(文字卡) | L0 | TODO | 占位 |  |
| P0 | `a-dufu-text` 杜甫在场(文字卡) | L0 | TODO | 占位 |  |
| P0 | `a-nar-arrive-city-sub` 字幕:这座城(CITY) | L0 | TODO | 占位 |  |
| P0 | `a-nar-arrive-person-sub` 字幕:这个人(PERSON) | L0 | TODO | 占位 |  |
| P0 | `a-nar-arrive-scene-sub` 字幕:眼前(SCENE) | L0 | TODO | 占位 |  |
| P0 | `a-nar-arrive-world-sub` 字幕:这个天下(WORLD) | L0 | TODO | 占位 |  |
| P0 | `a-nar-meet-dufu-sub` 字幕:杜甫台词(见) | L0 | TODO | 占位 |  |
| P0 | `a-nar-return-person-sub` 字幕:回——家书(PERSON) | L0 | TODO | 占位 |  |
| P0 | `a-nar-return-world-sub` 字幕:回——国破(WORLD) | L0 | TODO | 占位 |  |
| P0 | `a-recite-demo` 《春望》诵读示范(真人) | L2 | TODO | 占位 | ⚠ text |
| P0 | `a-recite-demo-subtitle` 诵读字幕(WebVTT) | L0 | TODO | 占位 |  |
| P1 | `a-chang-an-map` 长安示意地图 | L1 | TODO | 占位 | ⚠ scene_spec |
| P1 | `a-dufu-bust` 杜甫角色(正式版,替换占位) | L3 | TODO | 占位 |  |
| P1 | `a-dufu-still` 杜甫静帧(正式版) | L1 | TODO | 占位 |  |
| P1 | `a-nar-arrive-city` 旁白:这座城(CITY) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-arrive-person` 旁白:这个人(PERSON) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-arrive-scene` 旁白:眼前(SCENE) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-arrive-world` 旁白:这个天下(WORLD) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-meet-dufu` 杜甫台词(见) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-return-person` 旁白:回——家书(PERSON) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `a-nar-return-world` 旁白:回——国破(WORLD) | L2 | TODO | 占位 | ⚠ claims |
| P1 | `res-font-poem-serif` 诗句宋体/明朝体(子集) | — | TODO | 无 |  |
| P1 | `voice-dufu-1` 杜甫音色档案 | L2 | TODO | 占位 |  |
| P2 | `a-sfx-birds` 音效:鸟鸣(恨别鸟惊心) | L2 | TODO | 占位 |  |
| P2 | `a-sfx-birds-text` 音效:鸟鸣(文字卡) | L0 | TODO | 占位 |  |
| P2 | `res-font-calligraphy` 书法字体(诗题与落款字形,可选) | — | TODO | 无 |  |

### 需要用户先解决的卡点

- **scene_spec**(挡住 2 个任务:a-changan-dusk、a-chang-an-map):《春望》的场景要素表(地点、季节、时段、天气、可见物件、禁止出现项)尚未建立:查遍 docs/ 与 content-agent/ 只有设计文档提到它,没有数据。器物、服饰、建筑细节没有依据,不得派发给绘制方。建立后解除。
- **claims**(挡住 7 个任务:a-nar-arrive-scene、a-nar-arrive-city、a-nar-arrive-world、a-nar-arrive-person、a-nar-meet-dufu、a-nar-return-world、a-nar-return-person):bundle 里的台词依据的 claim 尚无可核查引文(facts.chun-wang.json 的 cited_claim_ids 为空,草稿状态)。文案定稿前不得派发录音。
- **text**(挡住 1 个任务:a-recite-demo):课本版原文、字音(尤其『胜』shèng)、停顿尚未与纸质课本核对(chun-wang-sample-spec §5/§8.4)。核对前不得派发真人诵读。

## 静夜思(李白,mock)

共 4 个任务。

状态:TODO 4

- 已有正式素材:**0**
- 仅有占位(不可上线):**4**
- 既无正式也无占位(前端走降级):**0**
- 暂不可派发(依据未定):**2**

| 优先级 | 任务 | 等级 | 状态 | 素材现状 | 暂不可派发 |
|---|---|---|---|---|---|
| P0 | `a-jys-moonlight` 月光(场景插画,概括轮廓) | L1 | TODO | 占位 | ⚠ scene_spec |
| P0 | `a-jys-moonlight-text` 月光(文字卡) | L0 | TODO | 占位 |  |
| P0 | `a-jys-recite` 《静夜思》诵读示范(真人) | L2 | TODO | 占位 | ⚠ text_version |
| P0 | `a-jys-recite-subtitle` 诵读字幕(WebVTT) | L0 | TODO | 占位 |  |

### 需要用户先解决的卡点

- **scene_spec**(挡住 1 个任务:a-jys-moonlight):《静夜思》的场景要素表不存在(与《春望》同样缺失,且这首诗更特殊:诗里只有月光、地上的白、抬头与低头)。尤其『床』指什么(卧具、坐具还是井栏)学界有不同说法,没有定论前,画面里不得出现任何床、窗、屋、家具;时间、地点、季节、天气也不得指明。
- **text_version**(挡住 1 个任务:a-jys-recite):诗句文本有多个流传版本,课本采用哪一版需要内容负责人对照纸质课本确认。确认前不得派发真人诵读,字幕和文字卡也只能暂用 mock 的一种版本。
- **claims**(挡住 0 个任务:—):台词引用的 claim(claim-jys-*)是 mock,不存在可核查的引文;『诗里的月光像霜』这类只依据诗句本身的解读,契约里没有『依据=作品文本』的表达方式,见 second-poem-playbook.md。

## 登记簿

30 项;登记检查:通过。
