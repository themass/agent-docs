# 任务单:《春望》诵读示范(真人)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-recite-demo` |
| 诗 | chun-wang |
| 类型 | recitation |
| 登记 kind / level | audio / L2(render: audio) |
| 优先级 | P0 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| ⚠ 暂不可派发 | 课本版原文、字音(尤其『胜』shèng)、停顿尚未与纸质课本核对(chun-wang-sample-spec §5/§8.4)。核对前不得派发真人诵读。 |

## 用途(= 登记 meaning)

示范停顿与韵律,学生知道这句该怎么读出来——对应全诗八句

- 用于步骤:recite;层:SCENE
- 对应诗句:第1句「国破山河在」、第2句「城春草木深」、第3句「感时花溅泪」、第4句「恨别鸟惊心」、第5句「烽火连三月」、第6句「家书抵万金」、第7句「白头搔更短」、第8句「浑欲不胜簪」
- bundle 引用位置:`steps[4].demo_audio`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `recite.m4a` | m4a | 是 | min_duration_ms=10000, max_duration_ms=60000, min_sample_rate=44100, max_bytes=900000 |
| script | `recite.txt` | txt | 是 | —<br>诵读所依据的原文逐句(UTF-8),用来人工核对读错字。 |

交付方式:把文件放进 `inbox/a-recite-demo/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-recite-demo`。

## 版权与来源要求

- delivery.json 必须填写:origin、license、evidence
- 可接受的来源:真人录音(须附朗读人授权);授权合成音(须写明模型、版本与授权范围);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:真人:朗读人书面授权/同意书编号;合成音:服务条款或授权书中覆盖商用的条款

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-recite-demo/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:recite.m4a(m4a) 必需;min_duration_ms=10000, max_duration_ms=60000, min_sample_rate=44100, max_bytes=900000
- [ ] script:recite.txt(txt) 必需
- [ ] 文字类交付物(字幕/文字卡/脚本)与任务单 brief.script_text 逐字一致(忽略空白)

### 人工验收

- [ ] 逐字对照 recite.txt,无读错字、多音字读音与课本注音一致(『胜』shèng 等,待纸质课本核对)
- [ ] 停顿和断句合理
- [ ] 无明显噪音/爆音/削波
- [ ] 朗读人的授权声明已收到
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用

## 降级关系

失效时降到 `a-recite-demo-subtitle`(必须严格低一级,最终到 L0 文字)。

## 创作说明

真人诵读,律诗节奏,语速适合学生跟读,不加配乐。需要小学版与初中版时各开一张任务单(本单为通用版,若分版请复制)。TTS 读古诗韵律不合格(architecture §2.3),不得用 TTS 作正式版。

- 性质:**史实**
- 依据:诗句全文;字音与停顿须与纸质课本核对后再派发。
- 风格/技术约束:
  - 真人诵读,语速适合学生跟读;小学/初中可各一版(各自一张任务单)
  - 停顿体现律诗的节奏;不加配乐
  - 录音环境安静,无削波
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹

### 逐字脚本(不得增删)

> 国破山河在,城春草木深。感时花溅泪,恨别鸟惊心。烽火连三月,家书抵万金。白头搔更短,浑欲不胜簪。

## 占位与状态机

- 占位策略:generated-audio(占位:macOS say 朗读,韵律不可信,不可上线)
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
