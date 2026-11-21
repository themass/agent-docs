# 任务单:《静夜思》诵读示范(真人)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-jys-recite` |
| 诗 | jing-ye-si |
| 类型 | recitation |
| 登记 kind / level | audio / L2(render: audio) |
| 优先级 | P0 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| ⚠ 暂不可派发 | 诗句文本有多个流传版本,课本采用哪一版需要内容负责人对照纸质课本确认。确认前不得派发真人诵读,字幕和文字卡也只能暂用 mock 的一种版本。 |

## 用途(= 登记 meaning)

示范停顿与韵律,学生知道这四句该怎么读出来——对应全诗四句

- 用于步骤:recite;层:SCENE
- 对应诗句:第1句「床前明月光」、第2句「疑是地上霜」、第3句「举头望明月」、第4句「低头思故乡」
- bundle 引用位置:`steps[3].demo_audio`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `recite.m4a` | m4a | 是 | min_duration_ms=4000, max_duration_ms=30000, min_sample_rate=44100, max_bytes=900000 |
| script | `recite.txt` | txt | 是 | —<br>诵读所依据的原文逐句(UTF-8),用来人工核对读错字。 |

交付方式:把文件放进 `inbox/a-jys-recite/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check jing-ye-si a-jys-recite`。

## 版权与来源要求

- delivery.json 必须填写:origin、license、evidence
- 可接受的来源:真人录音(须附朗读人授权);授权合成音(须写明模型、版本与授权范围);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:真人:朗读人书面授权/同意书编号;合成音:服务条款或授权书中覆盖商用的条款

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-jys-recite/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:recite.m4a(m4a) 必需;min_duration_ms=4000, max_duration_ms=30000, min_sample_rate=44100, max_bytes=900000
- [ ] script:recite.txt(txt) 必需
- [ ] 文字类交付物(字幕/文字卡/脚本)与任务单 brief.script_text 逐字一致(忽略空白)

### 人工验收

- [ ] 逐字对照 recite.txt,无读错字、多音字读音与课本注音一致(字音待纸质课本核对)
- [ ] 停顿和断句合理
- [ ] 无明显噪音/爆音/削波
- [ ] 朗读人的授权声明已收到
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用

## 降级关系

失效时降到 `a-jys-recite-subtitle`(必须严格低一级,最终到 L0 文字)。

## 创作说明

真人诵读,语速适合学生跟读,不加配乐。全诗只有四句,总时长比《春望》短得多,故时长下限放宽到 4 秒。TTS 读古诗韵律不合格,不得作正式版。

- 性质:**史实**
- 依据:诗句全文(mock 的一种版本,待核)。
- 风格/技术约束:
  - 真人诵读,语速适合学生跟读;小学/初中可各一版(各自一张任务单)
  - 停顿体现四句小诗的节奏;不加配乐
  - 录音环境安静,无削波
- 禁止出现:
  - 指明创作地点或创作年份(不可考,不展示)
  - 画出床、窗、屋宇、家具、人物或人物的剪影
  - 给月亮标注具体月相、季节、天气作为事实
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 把演绎当作史实呈现:李白当时的处境、心情、动作一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹

### 逐字脚本(不得增删)

> 床前明月光,疑是地上霜。举头望明月,低头思故乡。

## 占位与状态机

- 占位策略:generated-audio(占位:macOS say 朗读,韵律不可信,不可上线)
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
