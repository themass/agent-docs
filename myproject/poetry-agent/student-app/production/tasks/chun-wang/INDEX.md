# 春望(杜甫) 素材任务总表

> 由 `node tools/prod.mjs gen chun-wang` 生成;不要手改。规格来源:`demand.json` + `specs/kinds.json`。

| 优先级 | 任务 | 类型 | 等级 | 状态 | 占位 | 暂不可派发 |
|---|---|---|---|---|---|---|
| P0 | [`a-chang-an-map-text`](sheets/a-chang-an-map-text.md) 长安示意地图(文字卡) | text-card | L0 | TODO | 有 |  |
| P0 | [`a-changan-dusk`](sheets/a-changan-dusk.md) 春日长安(视差场景) | parallax-scene | L1 | TODO | 有 | 是 |
| P0 | [`a-changan-dusk-text`](sheets/a-changan-dusk-text.md) 春日长安(文字卡) | text-card | L0 | TODO | 有 |  |
| P0 | [`a-dufu-text`](sheets/a-dufu-text.md) 杜甫在场(文字卡) | text-card | L0 | TODO | 有 |  |
| P0 | [`a-nar-arrive-city-sub`](sheets/a-nar-arrive-city-sub.md) 字幕:这座城(CITY) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-arrive-person-sub`](sheets/a-nar-arrive-person-sub.md) 字幕:这个人(PERSON) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-arrive-scene-sub`](sheets/a-nar-arrive-scene-sub.md) 字幕:眼前(SCENE) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-arrive-world-sub`](sheets/a-nar-arrive-world-sub.md) 字幕:这个天下(WORLD) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-meet-dufu-sub`](sheets/a-nar-meet-dufu-sub.md) 字幕:杜甫台词(见) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-return-person-sub`](sheets/a-nar-return-person-sub.md) 字幕:回——家书(PERSON) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-nar-return-world-sub`](sheets/a-nar-return-world-sub.md) 字幕:回——国破(WORLD) | subtitle | L0 | TODO | 有 |  |
| P0 | [`a-recite-demo`](sheets/a-recite-demo.md) 《春望》诵读示范(真人) | recitation | L2 | TODO | 有 | 是 |
| P0 | [`a-recite-demo-subtitle`](sheets/a-recite-demo-subtitle.md) 诵读字幕(WebVTT) | subtitle | L0 | TODO | 有 |  |
| P1 | [`a-chang-an-map`](sheets/a-chang-an-map.md) 长安示意地图 | map | L1 | TODO | 有 | 是 |
| P1 | [`a-dufu-bust`](sheets/a-dufu-bust.md) 杜甫角色(正式版,替换占位) | character | L3 | TODO | 有 |  |
| P1 | [`a-dufu-still`](sheets/a-dufu-still.md) 杜甫静帧(正式版) | character-still | L1 | TODO | 有 |  |
| P1 | [`a-nar-arrive-city`](sheets/a-nar-arrive-city.md) 旁白:这座城(CITY) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-arrive-person`](sheets/a-nar-arrive-person.md) 旁白:这个人(PERSON) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-arrive-scene`](sheets/a-nar-arrive-scene.md) 旁白:眼前(SCENE) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-arrive-world`](sheets/a-nar-arrive-world.md) 旁白:这个天下(WORLD) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-meet-dufu`](sheets/a-nar-meet-dufu.md) 杜甫台词(见) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-return-person`](sheets/a-nar-return-person.md) 旁白:回——家书(PERSON) | narration | L2 | TODO | 有 | 是 |
| P1 | [`a-nar-return-world`](sheets/a-nar-return-world.md) 旁白:回——国破(WORLD) | narration | L2 | TODO | 有 | 是 |
| P1 | [`res-font-poem-serif`](sheets/res-font-poem-serif.md) 诗句宋体/明朝体(子集) | font | — | TODO | — |  |
| P1 | [`voice-dufu-1`](sheets/voice-dufu-1.md) 杜甫音色档案 | voice-profile | L2 | TODO | 有 |  |
| P2 | [`a-sfx-birds`](sheets/a-sfx-birds.md) 音效:鸟鸣(恨别鸟惊心) | sfx | L2 | TODO | 有 |  |
| P2 | [`a-sfx-birds-text`](sheets/a-sfx-birds-text.md) 音效:鸟鸣(文字卡) | text-card | L0 | TODO | 有 |  |
| P2 | [`res-font-calligraphy`](sheets/res-font-calligraphy.md) 书法字体(诗题与落款字形,可选) | font | — | TODO | — |  |

## 暂不可派发的原因

- **scene_spec**:《春望》的场景要素表(地点、季节、时段、天气、可见物件、禁止出现项)尚未建立:查遍 docs/ 与 content-agent/ 只有设计文档提到它,没有数据。器物、服饰、建筑细节没有依据,不得派发给绘制方。建立后解除。
- **claims**:bundle 里的台词依据的 claim 尚无可核查引文(facts.chun-wang.json 的 cited_claim_ids 为空,草稿状态)。文案定稿前不得派发录音。
- **text**:课本版原文、字音(尤其『胜』shèng)、停顿尚未与纸质课本核对(chun-wang-sample-spec §5/§8.4)。核对前不得派发真人诵读。
