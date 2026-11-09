# 角色与来源

## 角色卡

- `linche.v2.json` — 林澈，成长教练。
- `sudai.v2.json` — 苏黛，组织心理学家。

两张卡都是 SillyTavern Character Card V2 格式。平台私有字段放在 `extensions.vvv` 下，导入导出时原样带回。

## 来源与许可

人设改编自 [agency-agents-zh](https://github.com/msitarzewski/agency-agents)（MIT 许可，中文版由 jnMetaCode 维护）：

| 角色 | 原文件 |
|---|---|
| 林澈 | `specialized/personal-growth-mentor.md` |
| 苏黛 | `specialized/organizational-psychologist.md` |

改编内容：压缩为对话角色的人设字段，删除交付物模板与长篇框架说明，方法论移入 skill 包（`skills/public/growth-coaching`、`skills/public/org-psychology`）。原名与许可保留在此。

## 形象与音色

- `voice_ref` 的 `voice_id` 是占位值，接火山引擎时替换为实际音色 id。
- `model_ref` 指向简单动画渲染器的素材 id。素材尚未制作，渲染器缺图时回退到立绘。

## 新增角色

1. 在 `characters/` 放一张 V2 JSON。
2. 如果它需要新的方法论，在 `skills/public/<id>/` 建 skill 包，并在 `extensions.vvv.skill` 里引用。
3. 如果沿用已有 skill，直接引用即可。
