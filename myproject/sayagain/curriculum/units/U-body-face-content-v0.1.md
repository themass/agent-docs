# U-body-face-v0.1 内容包规格

> 状态：内容编审初稿。所有文本、音频、插画和例句在发布前必须经过英语语言审校、适龄审校和素材授权核验。

## 1. 内容对象原则

- 每个稳定内容对象有独立 ID 和版本；
- 具体词义与词形变化分开表达；
- `eye` 与 `eyes` 建立词形关联，不把复数当成完全无关的新词；
- 中文是理解支架，不是每道题的永久答案；
- 词条内容与活动实例分离，同一词可在不同主题/体验带复用。

## 2. 核心词对象

| ID | 英文 | 类型/词义 | 中文支架 | 发音占位 | 例句/短语 | 视觉/动作锚点 | 常见混淆 |
|---|---|---|---|---|---|---|---|
| `body.face.eye` | eye | 名词，眼睛（单数） | 眼睛 | /aɪ/ | This is my eye. | Milo 指向一只眼睛 | ear, mouth |
| `body.face.ear` | ear | 名词，耳朵（单数） | 耳朵 | /ɪr/ | This is my ear. | Milo 做听的动作并指耳朵 | eye |
| `body.face.nose` | nose | 名词，鼻子 | 鼻子 | /noʊz/ | This is my nose. | Milo 指向鼻子 | mouth |
| `body.face.mouth` | mouth | 名词，嘴巴 | 嘴巴 | /maʊθ/ | This is my mouth. | Milo 指向嘴巴 | nose |
| `body.face.face` | face | 名词，脸/面部整体 | 脸 | /feɪs/ | This is my face. | 镜子/脸部整体轮廓 | body |

发音标注为内容制作占位，正式音频由目标口音、年龄适配和语言审校确定；不得只依据表格中的 IPA 自动生成上线音频。

## 3. 指令与句块对象

| ID | 英文 | 中文支架 | 目标 | 允许的替代/说明 |
|---|---|---|---|---|
| `body.command.touch-your-nose` | Touch your nose. | 摸一摸你的鼻子。 | 指令理解、动作句块 | 点图替代真实动作 |
| `body.command.open-your-mouth` | Open your mouth. | 张开你的嘴巴。 | 指令理解、动作句块 | 只选动作图，不要求拍摄 |
| `body.command.close-your-eyes` | Close your eyes. | 闭上你的眼睛。 | 指令理解；eyes 与 eye 关联 | 注意安全，不要求长时间闭眼 |
| `body.question.where-nose` | Where is your nose? | 你的鼻子在哪里？ | 受控理解、亲子问答 | 可只点图，不强制口头答 |
| `body.statement.this-eye` | This is my eye. | 这是我的眼睛。 | 句块理解、跟说 | 不代表自由造句 |

## 4. 内容关系

```text
body.face.eye ──related-form── body.face.eyes
body.face.eye ──used-in── body.statement.this-eye
body.face.nose ──used-in── body.command.touch-your-nose
body.face.mouth ──used-in── body.command.open-your-mouth
body.face.eye ──used-in── body.command.close-your-eyes
body.face.* ──belongs-to── theme.body-and-face
body.face.* ──reappears-in── theme.zoo-and-human-relations（后续，可做动物身体比较）
```

## 5. 活动配置样例

### 5.1 示范活动

```yaml
id: act.body-face.demo.eye.v1
activity_template: tutor-demonstrate
experience_bands: [P0, P1]
content_ids: [body.face.eye]
goal_ids: [G-face-listen, G-face-recognize]
tutor_action: point(eye)
answer_revealed: true
counts_as_mastery: false
```

### 5.2 无提示听辨

```yaml
id: act.body-face.audio-hotspot.v1
activity_template: audio-hotspot
content_ids: [body.face.eye, body.face.ear, body.face.nose, body.face.mouth]
goal_ids: [G-face-listen]
tutor_action: idle
visible_text: false
highlight_target: false
hint_limit: 1
evidence: independent_audio_selection
```

### 5.3 指令理解

```yaml
id: act.body-face.instruction-choice.v1
activity_template: instruction-choice
content_ids: [body.command.touch-your-nose]
goal_ids: [G-face-command, G-face-chunk]
demonstration_first: true
assessment_mode: audio_to_action_image
camera_required: false
```

## 6. 干扰项规则

- 干扰项必须来自已学或明确可理解的同主题内容；
- 不用生僻词、拼写陷阱或文化知识制造难度；
- 同一题只能有一个与目标条件匹配的答案；
- P0 选项不超过 2 个；P1 可逐步增加到 3 个；
- 音频题不能让干扰项因长度、位置或颜色明显暴露；
- 身体图需保持安全、尊重和非医疗化的表现方式。

## 7. 适龄变体

| 内容元素 | P0 | P1 | P2/P3 后续 |
|---|---|---|---|
| 解释 | 中文+动作 | 中文可选+短英文 | 英文情境，中文按需 |
| 图像 | 清晰、单对象、大热点 | 场景中找部位 | 健康/运动/看医生场景 |
| 词形 | 可隐藏 | 显示目标词 | 词形变化、短句阅读 |
| 口头 | 跟说或跳过 | 跟说/短回应 | 受控对话、描述 |
| 写作 | 不做 | 不做或描线 | 句子、短文本 |

## 8. 内容验收

- [ ] 词义、单复数、发音、例句经过审校；
- [ ] 所有图片热点与目标一致；
- [ ] 例句适龄且没有不必要文化负担；
- [ ] 音频速度和停顿可供儿童跟随；
- [ ] 指令与动作图只有一个合理答案；
- [ ] 已标注内容来源、授权和版本；
- [ ] 不能用一次题目结果宣称说、写或真实动作能力。
