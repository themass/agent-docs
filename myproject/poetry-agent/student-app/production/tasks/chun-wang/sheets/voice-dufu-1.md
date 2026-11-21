# 任务单:杜甫音色档案

| 项 | 值 |
|---|---|
| 任务/素材 id | `voice-dufu-1` |
| 诗 | chun-wang |
| 类型 | voice-profile |
| 登记 kind / level | voice / L2(render: audio) |
| 优先级 | P1 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |

## 用途(= 登记 meaning)

让“杜甫”开口时有稳定的音色身份,而不是每次换一种声音

- 用于步骤:meet;层:PERSON
- 对应诗句:第7句「白头搔更短」、第8句「浑欲不胜簪」
- bundle 引用位置:`cast[0].voice_id`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `voice.json` | json | 是 | max_bytes=6000 |
| sample | `sample.m4a` | m4a | 是 | min_duration_ms=3000, max_duration_ms=20000, min_sample_rate=22050, max_bytes=300000 |

交付方式:把文件放进 `inbox/voice-dufu-1/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang voice-dufu-1`。

## 版权与来源要求

- delivery.json 必须填写:origin、license、evidence
- 可接受的来源:授权合成音(须写明模型、版本与授权范围);真人音色(须附书面授权);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:真人:朗读人书面授权/同意书编号;合成音:服务条款或授权书中覆盖商用的条款

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/voice-dufu-1/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:voice.json(json) 必需;max_bytes=6000
- [ ] sample:sample.m4a(m4a) 必需;min_duration_ms=3000, max_duration_ms=20000, min_sample_rate=22050, max_bytes=300000

### 人工验收

- [ ] 授权范围写明商用
- [ ] 试听与角色气质相符
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用
- [ ] 已确认界面会带『演绎』标识,素材本身不冒充史料

## 降级关系

失效时降到 `a-recite-demo-subtitle`(必须严格低一级,最终到 L0 文字)。

## 创作说明

确定一个音色(真人或授权合成),成年男声,语速偏缓,语气克制,不夸张。若用合成音,需记录模型、版本、参数以便复现,并确认授权覆盖商用。若克隆真人,需该真人的书面授权。

- 性质:**演绎(界面需带「演绎」标识,不得当作史实)**
- 依据:产品规则:角色音色需稳定(architecture §2.3)。无史料依据其嗓音,故为演绎。
- 风格/技术约束:
  - voice.json 写明:提供者/模型/版本/参数、授权范围、是否允许克隆
  - 音色一经确定不得每次更换
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹

## 占位与状态机

- 占位策略:generated-audio(占位:macOS say 合成,不可上线,授权未核实)
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
