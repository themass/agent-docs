# 静夜思(李白,mock) 素材任务总表

> 由 `node tools/prod.mjs gen jing-ye-si` 生成;不要手改。规格来源:`demand.json` + `specs/kinds.json`。

| 优先级 | 任务 | 类型 | 等级 | 状态 | 占位 | 暂不可派发 |
|---|---|---|---|---|---|---|
| P0 | [`a-jys-moonlight`](sheets/a-jys-moonlight.md) 月光(场景插画,概括轮廓) | scene-illustration | L1 | TODO | 有 | 是 |
| P0 | [`a-jys-moonlight-text`](sheets/a-jys-moonlight-text.md) 月光(文字卡) | text-card | L0 | TODO | 有 |  |
| P0 | [`a-jys-recite`](sheets/a-jys-recite.md) 《静夜思》诵读示范(真人) | recitation | L2 | TODO | 有 | 是 |
| P0 | [`a-jys-recite-subtitle`](sheets/a-jys-recite-subtitle.md) 诵读字幕(WebVTT) | subtitle | L0 | TODO | 有 |  |

## 暂不可派发的原因

- **scene_spec**:《静夜思》的场景要素表不存在(与《春望》同样缺失,且这首诗更特殊:诗里只有月光、地上的白、抬头与低头)。尤其『床』指什么(卧具、坐具还是井栏)学界有不同说法,没有定论前,画面里不得出现任何床、窗、屋、家具;时间、地点、季节、天气也不得指明。
- **text_version**:诗句文本有多个流传版本,课本采用哪一版需要内容负责人对照纸质课本确认。确认前不得派发真人诵读,字幕和文字卡也只能暂用 mock 的一种版本。
- **claims**:台词引用的 claim(claim-jys-*)是 mock,不存在可核查的引文;『诗里的月光像霜』这类只依据诗句本身的解读,契约里没有『依据=作品文本』的表达方式,见 second-poem-playbook.md。
