# 任务单:春日长安(视差场景)

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-changan-dusk` |
| 诗 | chun-wang |
| 类型 | parallax-scene |
| 登记 kind / level | illustration / L1(render: parallax) |
| 优先级 | P0 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| ⚠ 暂不可派发 | 《春望》的场景要素表(地点、季节、时段、天气、可见物件、禁止出现项)尚未建立:查遍 docs/ 与 content-agent/ 只有设计文档提到它,没有数据。器物、服饰、建筑细节没有依据,不得派发给绘制方。建立后解除。 |

## 用途(= 登记 meaning)

让学生感到“城还在,但已经残破”——对应『国破山河在,城春草木深』

- 用于步骤:arrive、recite;层:SCENE
- 对应诗句:第1句「国破山河在」、第2句「城春草木深」
- bundle 引用位置:`steps[1].layers[0].assets`、`steps[4].layers[0].assets`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `parallax.json` | json | 是 | json_schema=parallax-manifest, max_bytes=8000 |
| layer | `layers/*` | svg/png/webp | 是 | max_bytes=350000, alpha=true, svg_viewbox_equals_canvas=true, no_script=true |
| poster | `poster.webp` | webp | 是 | min_width=1280, min_height=720, aspect=16:9, max_bytes=450000<br>所有层合成的静帧,弱网/减少动效时使用。 |

交付方式:把文件放进 `inbox/a-changan-dusk/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-changan-dusk`。

## 版权与来源要求

- delivery.json 必须填写:origin、license
- 可接受的来源:自绘;外包绘制;AI 生成(须写明模型与版本,且经人工修复);自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:外包:合同编号;AI 生成:工作流 JSON@hash;自绘:作者声明

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-changan-dusk/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:parallax.json(json) 必需;json_schema=parallax-manifest, max_bytes=8000
- [ ] layer:layers/*(svg/png/webp) 必需,至少 3 个,至多 6 个;max_bytes=350000, alpha=true, svg_viewbox_equals_canvas=true, no_script=true
- [ ] poster:poster.webp(webp) 必需;min_width=1280, min_height=720, aspect=16:9, max_bytes=450000

### 人工验收

- [ ] 拼合后与 poster 一致
- [ ] 移动时无『纸片感』:远近层级合理
- [ ] 每一层单独看都不含禁止出现的物件
- [ ] 减少动效模式下 poster 单独可用
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用
- [ ] 已确认界面会带『演绎』标识,素材本身不冒充史料

## 降级关系

失效时降到 `a-changan-dusk-text`(必须严格低一级,最终到 L0 文字)。

## 创作说明

春天的长安城,远处有山,中景是城郭的概括轮廓,近景是长得很深的草木。画面重点是落差:城还在,但静;草木很盛,人很少。色调取淡墨与宣纸底,少量青绿;不要鲜艳。分 4–5 层(天空/远山/城郭/草木/近草),便于视差。

- 性质:**演绎(界面需带「演绎」标识,不得当作史实)**
- 依据:诗句『国破山河在,城春草木深』(山河、城、春、草木);bundle SCENE 层台词『城还在,但城门和城墙像是烧过又重新修过』属 INTERPRETATION,依据 claim-bg-scene 尚未核查。『烧过又修过』的具体痕迹没有场景要素表依据,画面不得具体描绘,只用概括的残旧感。
- 风格/技术约束:
  - 层从远到近:天空/远山/中景(城郭)/近景(草木),每层透明背景
  - 层间相对位移由 parallax.json 的 depth(0=不动,1=最大)给出,不超过 ±3% 画布宽度
  - 同风格同色板,层与层拼合后无明显接缝
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹
  - 画出人物
  - 画出战争场面、尸体、血迹、武器、旗帜
  - 写实的建筑纹样

## 占位与状态机

- 占位策略:generated-svg
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
