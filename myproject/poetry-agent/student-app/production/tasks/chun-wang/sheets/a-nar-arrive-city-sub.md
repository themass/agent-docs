# 任务单:字幕:这座城(CITY)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-nar-arrive-city-sub` |
| 诗 | chun-wang |
| 类型 | subtitle |
| 登记 kind / level | subtitle / L0(render: subtitle-track) |
| 优先级 | P0 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| 降级伴生于 | `a-nar-arrive-city` |
| 依赖 | `a-nar-arrive-city` |

## 用途(= 登记 meaning)

旁白不可用时,这一层的文字仍完整可读

- 用于步骤:arrive;层:CITY
- 对应诗句:第1句「国破山河在」、第2句「城春草木深」
- bundle 引用位置:`assets.a-nar-arrive-city.fallback`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `captions.vtt` | vtt | 是 | vtt_monotonic=true, max_bytes=20000 |

交付方式:把文件放进 `inbox/a-nar-arrive-city-sub/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-nar-arrive-city-sub`。

## 版权与来源要求

- delivery.json 必须填写:origin、license
- 可接受的来源:由底座/剧本文本派生;自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:外包:合同编号;AI 生成:工作流 JSON@hash;自绘:作者声明

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-nar-arrive-city-sub/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:captions.vtt(vtt) 必需;vtt_monotonic=true, max_bytes=20000
- [ ] 文字类交付物(字幕/文字卡/脚本)与任务单 brief.script_text 逐字一致(忽略空白)

### 人工验收

- [ ] 文字与音频一致
- [ ] 断句合理
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用

## 降级关系

这是降级终点(L0 文字)或不参与降级。

## 创作说明

一条字幕,文字与对应音频脚本逐字一致,时间轴依据音频实际时长。

- 性质:**史实**
- 依据:同 a-nar-arrive-city。
- 风格/技术约束:
  - 字幕文本必须与对应音频的脚本逐字一致
  - 每条 ≤ 34 字(DESIGN.md 版心),时间递增不重叠
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹

### 逐字脚本(不得增删)

> 叛军攻下长安之后，杜甫被困在这座城里。

## 占位与状态机

- 占位策略:generated-vtt
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
