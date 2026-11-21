# 离线生产:将来有 GPU 或外包时怎么接入

- 日期:2026-11-06;状态:方案稿。
- 前提(已定):**现在不做 GPU 生产**。素材靠「提前建好任务单,由用户/外包/将来的 GPU 流程交付」。本文只规定接口,不要求现在有任何 GPU。
- 原则:交付方是谁并不重要,**任务单、落点、机检、验收、入库是同一条流水线**。GPU 流程只是众多「交付人」之一。

## 1. 一条流水线

```
demand.json ──gen──▶ tasks.json + sheets/*.md          (任务单:规格、来源要求、验收标准、创作说明)
                          │ 派发(state … DISPATCHED --assignee <谁>)
                          ▼
         交付人(用户 / 外包 / GPU 流程)把文件放进 inbox/<task_id>/ 并附 delivery.json
                          │ check(机检:格式、尺寸、大小、时长、hash、授权声明、文字一致性)
                          ▼
            AUTO_PASSED ──人工验收(逐条勾选 acceptance.human,验收人≠交付人)──▶ HUMAN_ACCEPTED
                          │ publish
                          ▼
   published/assets/<id>/… + registry.json + bundles/<poem>.assets.json(给 bundle 的引用)
```

任何一步不通过 → REJECTED(写明原因)→ 重新派发。机检不通过的交付物到不了人工验收。

命令:

```bash
node tools/prod.mjs gen chun-wang                                  # 生成/刷新任务单
node tools/prod.mjs state chun-wang a-changan-dusk DISPATCHED --assignee 外包A
node tools/prod.mjs init-delivery chun-wang a-changan-dusk         # 交付人拿到 delivery.json 模板
node tools/prod.mjs check chun-wang a-changan-dusk                 # 机检;通过→AUTO_PASSED
node tools/prod.mjs state chun-wang a-changan-dusk HUMAN_ACCEPTED --by 验收人 --note "逐条通过"
node tools/prod.mjs publish chun-wang a-changan-dusk               # 入库并登记
node tools/prod.mjs report chun-wang                               # 进度
```

## 2. GPU 流程怎么接

GPU 流程(ComfyUI、TTS 服务等)**不直接写 published/ 或 registry.json**,只做三件事:

1. 读 `tasks/<poem>/tasks.json` 里自己领取的任务(`brief.creative_notes`、`brief.script_text`、`deliverables`)。
2. 把产出写进 `inbox/<task_id>/`,按 `deliverables[].filename` 命名。
3. 写 `delivery.json`:`author`(流程名)、`rights.origin`(写明模型与版本)、`rights.workflow`(工作流文件 + hash)、`rights.human_fix`、`evidence`。

### 2.1 提示词与工作流存放

```
production/workflows/                  # 目录待建(首次接入时创建;现在没有)
  <poem>/<asset_id>/
    prompt.md                          # 最终使用的提示词(正向/负向),逐字保存
    workflow.json                      # ComfyUI 工作流 JSON(或 TTS 参数 JSON)
    models.json                        # 模型名、版本、hash、许可(没有就写「未知」,不要省略)
    seed.txt                           # 种子与参数,保证可复现
    reference/                         # 参考图(只放有授权的)
```

`delivery.json` 的 `rights.workflow` 写成 `workflows/<poem>/<asset_id>/workflow.json@<sha256>`。这样登记簿里的 `workflow_ref` 能追到当时的工作流(Java 的 `poetry_asset.workflow_ref` 就是这个字段)。

要求:

- 提示词不得要求画任务单 `forbidden_elements` 里的内容;器物、服饰、建筑必须依据场景要素表(现在还没有这张表,见第 5 节)。
- AI 生成的图像必须 `human_fix`,不能把未经人看过的生成结果直接入库。
- 模型的许可必须写进 `models.json`;许可不明的模型产出不得入库。

### 2.2 机检会拦什么(已实现)

| 检查 | 位置 |
|---|---|
| 文件存在、格式正确(文件头) | `tools/lib/checks.mjs` |
| 文件大小上限 | 同上(`max_bytes`) |
| 图片宽高、宽高比、透明通道(PNG/WebP/JPEG/SVG) | 同上 |
| SVG 无脚本/事件属性/外部引用,viewBox 等于画布 | 同上 |
| 音频时长、采样率、声道(WAV 自解析;m4a/mp3 用 ffprobe,**没有 ffprobe 则这一项给警告,不会静默通过**) | 同上 |
| 字幕 WebVTT 格式、时间递增不重叠、每条 ≤ 34 字 | 同上 |
| 字幕/文字卡与任务单脚本逐字一致 | `tools/prod.mjs` |
| 视差/角色/音色 JSON 过 schema,引用的文件已交付 | `tools/lib/checks.mjs`、`tools/character-check.mjs` |
| `delivery.json` 完整(来源、授权、交付人)且没有禁止的来源 | `tools/lib/checks.mjs` |
| 登记簿:hash 唯一、降级链严格降层且到 L0、无环、bytes 与 hash 与文件一致 | `tools/lib/registry.mjs` |

机检**不能**判断的(留给人工):画面是否传达了 meaning、音频内容是否与脚本一致、读音是否正确、形象是否有无依据的细节、版权证明是否真实。

## 3. 外包怎么接

1. 用户在任务单上写 `--assignee <外包方>` 派发(带暂缓标记的任务派发会被拒绝,见第 5 节)。
2. 把 `tasks/<poem>/sheets/<task_id>.md`(含规格、版权要求、验收标准、创作说明)和 `contracts/` 里相关 schema 发给外包方。角色类附 `design/2d-character.md` 的需求单与 bible。
3. 外包按 `inbox/<task_id>/` 的结构交付(压缩包解开后放进去),并填 `delivery.json`。
4. 用户或脚本运行 `check`;失败原因会写进状态历史,可直接转给外包。
5. 人工验收人不能与交付人相同。

## 4. 用户需要提供什么(清单)

**没有这些,对应任务只能停在占位。**

### 4.1 决定与定稿

| 项 | 为什么需要 | 卡住的任务 |
|---|---|---|
| **《春望》场景要素表**(地点、季节、时段、天气、可见物件、禁止出现项) | 器物/服饰/建筑不得凭空想象。docs 里只有设计文字,没有数据,我没有找到这张表 | 场景插画、地图、角色服饰 |
| **台词定稿与引文核查**(bundle 里的台词依据的 claim 目前没有可核查引文) | 旁白和杜甫台词的文案变了,已录音频就作废 | 7 条旁白/台词音频 |
| **课本版原文、注音、停顿的核对结果**(纸质课本;尤其「胜」shèng) | 诵读示范是学生听到的「标准」 | 诵读示范 |
| **年龄口径**:已统一为「四十多岁」(OQ-06,2026-11-11 定) | 已解决。精确岁数无确证,不写进台词;出处区标「年岁无确证」 | PERSON 旁白 |
| **角色 bible 定稿** | 美术才能开始 | 杜甫角色 |
| 是否采用音效(P2) | 目前 bundle 没有引用 | 鸟鸣音效 |

### 4.2 素材与授权

| 项 | 要求 |
|---|---|
| **美术风格参考** | 3–5 张你喜欢的参考图,并说明是否有使用授权;来源不明的不要给 |
| **真人诵读录音** | 小学版/初中版各一条(是否分版由你定);朗读人的**书面同意书**,写明可商用、可用于网页与 App |
| **授权字体** | 诗句衬线体(必需,子集化前先确认授权覆盖商用+网页嵌入+子集化);书法字体(可选)。**字体授权我没有核实** |
| **音色** | 杜甫的音色选择;若用合成音,服务条款里覆盖商用的条款;若用真人音色,书面授权 |
| **授权声明模板** | 外包合同/个人声明里写明:作者、授权范围(商用、可修改、可再分发、永久)、是否使用 AI、第三方素材来源 |
| **Live2D / Spine 许可核实**(如要走外包角色) | 条款我没有核实,见 `2d-character.md` 第 9 节 |

### 4.3 运营决定

- 谁是验收人(不能与交付人相同)。
- 小学版与初中版诵读/旁白是否分开(分开则任务单加倍)。
- 占位素材在哪些渠道可见(建议:仅开发与内测;`placeholder.not_for_release=true` 的素材不得出现在生产渠道)。

## 5. 暂缓标记(dispatch_hold)

`demand.json` 的 `holds` 记录了「依据未定、不得派发」的原因,任务单与进度报告都会醒目标出,`state … DISPATCHED` 会拒绝派发(`--override-hold --note 理由` 可强行,留痕)。当前三项:

- `scene_spec`:场景要素表缺失。
- `claims`:台词依据的 claim 无可核查引文。
- `text`:课本原文与注音未核对。

解除方法:用户补齐依据后,在 `demand.json` 里删掉对应任务的 `hold` 字段,重新 `gen`。

## 6. 占位素材的规则

- 占位素材用**正式的 asset_id** 登记,`placeholder.is_placeholder=true`、`not_for_release=true`,`rights.license` 写「自有占位,不可上线」。
- 对应任务保持 TODO,直到真素材走完状态机并 `publish`;`publish` 会以同一 asset_id 覆盖占位登记(hash 变化)。
- 占位素材**不进入 Java `poetry_asset`**:它们只服务于学生端联调。要把正式素材同步到 Java,由 A 或用户走 `createAsset`;本目录对 Java 只读,不写库。
- 将来发布闸门应拒绝 `not_for_release=true` 的素材进入生产渠道(**这一闸门尚未实现**,目前靠 registry 字段与报告提示)。

## 7. 将来要补的(现在没有)

- `production/workflows/` 目录与 GPU 流程的实际适配脚本(没有 GPU,不做)。
- 把 registry 同步到 Java `createAsset` 的导入脚本(需要用户授权访问写接口;按约定不碰真实库)。
- 发布闸门对 `not_for_release` 的强制拦截。
- 多首诗:`demand.json` 是每首一份,`gen` 对任何放进 `tasks/<poem>/` 的 demand 都能工作,但目前只有《春望》一首。
