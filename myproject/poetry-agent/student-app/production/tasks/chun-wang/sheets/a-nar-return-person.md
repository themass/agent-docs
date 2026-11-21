# 任务单:旁白:回——家书(PERSON)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-nar-return-person` |
| 诗 | chun-wang |
| 类型 | narration |
| 登记 kind / level | audio / L2(render: audio) |
| 优先级 | P1 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| ⚠ 暂不可派发 | bundle 里的台词依据的 claim 尚无可核查引文(facts.chun-wang.json 的 cited_claim_ids 为空,草稿状态)。文案定稿前不得派发录音。 |

## 用途(= 登记 meaning)

让学生听到『抵万金』为什么有分量,落回第六句

- 用于步骤:return;层:PERSON
- 对应诗句:第6句「家书抵万金」
- bundle 引用位置:`steps[3].layers[1].lines[0]`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `narration.m4a` | m4a | 是 | min_duration_ms=1500, max_duration_ms=30000, min_sample_rate=22050, max_bytes=400000 |
| script | `narration.txt` | txt | 是 | — |

交付方式:把文件放进 `inbox/a-nar-return-person/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-nar-return-person`。

## 版权与来源要求

- delivery.json 必须填写:origin、license、evidence
- 可接受的来源:真人录音(须附朗读人授权);授权合成音(须写明模型、版本与授权范围);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:真人:朗读人书面授权/同意书编号;合成音:服务条款或授权书中覆盖商用的条款

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-nar-return-person/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:narration.m4a(m4a) 必需;min_duration_ms=1500, max_duration_ms=30000, min_sample_rate=22050, max_bytes=400000
- [ ] script:narration.txt(txt) 必需
- [ ] 文字类交付物(字幕/文字卡/脚本)与任务单 brief.script_text 逐字一致(忽略空白)

### 人工验收

- [ ] 与 narration.txt 逐字一致
- [ ] 音色符合 voice-profile
- [ ] 音量与诵读示范一致(±3dB)
- [ ] 无明显合成痕迹或爆音
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用

## 降级关系

失效时降到 `a-nar-return-person-sub`(必须严格低一级,最终到 L0 文字)。

## 创作说明

旁白音色。这是解释。

- 性质:**解释**
- 依据:bundle 台词 kind=INTERPRETATION,basis=claim-bg-person。
- 风格/技术约束:
  - 逐字念 narration.txt,不增删;文本来自 bundle 的 lines,改文案必须先改剧本
  - 『演绎』台词必须由角色音色念出,旁白不得念演绎台词
  - 语气平实,不用评价性形容词(悲惨/伟大/不朽)
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹

### 逐字脚本(不得增删)

> 家书到不了，“抵万金”才有分量。

## 占位与状态机

- 占位策略:generated-audio
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
