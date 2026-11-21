# 任务单:长安示意地图

| 项 | 值 |
|---|---|
| 任务/素材 id | `a-chang-an-map` |
| 诗 | chun-wang |
| 类型 | map |
| 登记 kind / level | map / L1(render: still) |
| 优先级 | P1 |
| 当前状态 | **TODO** |
| 占位素材 | 已有占位(不可上线),等待正式交付替换 |
| ⚠ 暂不可派发 | 《春望》的场景要素表(地点、季节、时段、天气、可见物件、禁止出现项)尚未建立:查遍 docs/ 与 content-agent/ 只有设计文档提到它,没有数据。器物、服饰、建筑细节没有依据,不得派发给绘制方。建立后解除。 |

## 用途(= 登记 meaning)

让学生知道长安的规模与位置——对应『城春草木深』里的『城』

- 用于步骤:arrive;层:CITY
- 对应诗句:第1句「国破山河在」、第2句「城春草木深」
- bundle 引用位置:`steps[1].layers[1].assets`

## 交付物与规格

| 角色 | 文件名 | 格式 | 必需 | 约束 |
|---|---|---|---|---|
| entry | `map.svg` | svg | 是 | max_bytes=120000, no_script=true |

交付方式:把文件放进 `inbox/a-chang-an-map/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check chun-wang a-chang-an-map`。

## 版权与来源要求

- delivery.json 必须填写:origin、license
- 可接受的来源:自绘;外包绘制;自生成占位
- 不接受:来源不明、网络下载、网图、盗版
- 证明材料:外包:合同编号;AI 生成:工作流 JSON@hash;自绘:作者声明

## 验收标准

### 机检(脚本自动执行)

- [ ] 交付目录 inbox/a-chang-an-map/ 含 delivery.json(来源、授权、交付人)
- [ ] entry:map.svg(svg) 必需;max_bytes=120000, no_script=true

### 人工验收

- [ ] 每个标注的地名都能在底座地点条目里找到
- [ ] 写明『示意图』
- [ ] 没有凭空添加的城门、坊市、宫殿名
- [ ] 版权:delivery.json 的来源与授权真实、完整、覆盖商用

## 降级关系

失效时降到 `a-chang-an-map-text`(必须严格低一级,最终到 L0 文字)。

## 创作说明

示意图而非考据复原:一个城郭方框、注明『长安』,标出内容底座已发布的相关地点(待 place-chang-an 发布后取其关联地点)。图上写明『示意图,不按比例』。

- 性质:**解释**
- 依据:bundle CITY 层台词『这是帝国都城,不是边地小城』(FACT,claim-bg-city 未核查);place-chang-an 目前是草稿。不得添加底座没有的城门、坊市、宫殿名。
- 风格/技术约束:
  - 地图是『示意』,必须在图上或图注写明『示意图,不按比例』
  - 地名、方位只能来自内容底座已发布的地点条目,不得自行添加
  - 文字用 font-family 的系统回退链,不嵌入未授权字体
- 禁止出现:
  - 画面中出现文字、印章、落款(文字由前端排印)
  - 可辨认的真实人物面部或肖像
  - 任何没有场景要素表依据的服饰、兵器、旗帜、器物、建筑形制细节(城墙/城门只画概括轮廓)
  - 把演绎当作史实呈现:天气、动作、心理、对白一律不得带『据记载』的口吻
  - 来源不明的参考图、他人作品的描摹
  - 自行添加底座没有的地名
  - 把示意图画成精确复原图

## 占位与状态机

- 占位策略:generated-svg
- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。
