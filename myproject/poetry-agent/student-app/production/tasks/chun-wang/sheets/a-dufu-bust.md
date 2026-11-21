# 任务单:杜甫角色(正式版,替换占位)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-dufu-bust` |
| 诗 | chun-wang |
| 类型 | character |
| 登记 kind / level | character / L3(render: character-svg-layers) |
| 优先级 | P1 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |

## 用途(= 登记 meaning)

让学生见到此时此地的诗人,而不是一个通用古人像

- 用于步骤:meet;层:PERSON
- 对应诗句:第7句「白头搔更短」、第8句「浑欲不胜簪」
- bundle 引用位置:`cast[0].avatar_asset`、`steps[2].roleplay.layers[0].assets`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `manifest.json` | json | 是 | json_schema=character, max_bytes=60000 |
| layer | `layers/*` | svg/png/webp/moc3/json/skel/atlas | 否 | — |
| poster | `still.*` | svg/png/webp | 是 | max_bytes=400000 |

交付方式:把文件放进 `inbox/a-dufu-bust/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-dufu-bust`。

## 版权与来源要求

- delivery.json 必须填写:origin、license
- 可接受的来源:自绘;外包制作;AI 辅助(须写明且经人工修复);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:外包:合同编号;AI 生成:工作流 JSON@hash;自绘:作者声明

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-dufu-bust/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:manifest.json(json) 必需;json_schema=character, max_bytes=60000
- [ ] layer:layers/*(svg/png/webp/moc3/json/skel/atlas) 可选
- [ ] poster:still.*(svg/png/webp) 必需;max_bytes=400000

### 人工验收

- [ ] 四个状态都能播放,切换无跳变
- [ ] 说话时不要求口型对齐,但动作不得诡异
- [ ] 形象没有无依据的服饰/器物细节(对照场景要素表)
- [ ] manifest.rights 写明来源与第三方运行库许可
- [ ] 包体 ≤ budget.max_bytes
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用
- [ ] 已确认界面会带『演绎』标识,素材本身不冒充史料

## 降级关系

失效时降到 `a-dufu-still`(必须严格低一级,最终到 L0 文字)。

## 创作说明

按角色 bible 绘制(见 design/2d-character.md 的模板;bible 需用户先定稿并提供风格参考)。必须含 idle/talk/sorrow/bow,可有 listen。形象为演绎,界面带标识。外包可选 Live2D / Spine / Lottie / 分层 SVG(许可条款待核实,见 2d-character.md)。

- 性质:**演绎(界面需带「演绎」标识,不得当作史实)**
- 依据:没有可靠的诗人画像可依据。年龄:写『四十多岁』,不写精确岁数(OQ-06,2026-11-11 已定)。角色不得被刻画成确切年龄。服饰须等场景要素表。
- 风格/技术约束:
  - 风格与角色 bible 一致(见 design/2d-character.md 模板)
  - 形象一律标识为演绎(manifest.depiction)
  - 必须含 idle/talk/sorrow/bow 四个状态,可有 listen
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹
  - 依据网上流传的杜甫画像描摹(版权与史实均不明)
  - 在没有场景要素表的情况下画官服品级

## 占位与状态机

- 占位策略:existing(占位已由里程碑 1 生成并登记(published/characters/du-fu))
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
