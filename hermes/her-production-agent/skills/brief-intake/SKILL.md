---
name: brief-intake
description: 用户只有一个模糊想法（「给我做个酷一点的歌姬」「她应该会说唱」）时，把想法整理成 her-drill 能直接吃的结构化 brief，并补齐用户没说但契约必须要的字段。
version: 0.1.0
author: hermes-her-production (drill)
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [her, brief, intake]
---

# brief-intake —— 模糊想法 → 结构化 brief

## 要凑齐的字段（对照 `her-production.sh new` 的 flag）

| 字段 | 用户没说时 |
|---|---|
| name | 从想法里取一个；别自己瞎编名字，用 `clarify` 问 |
| asset（= pack_id） | 你提议一个拉丁 slug（如 `kira-songstress`），让用户确认 |
| tagline | 一句话卖点，你来写，用户可改 |
| personality | 你来扩写（2–4 句），必须过 `clarify` 或用户确认后才进产线 |
| first_mes | 角色第一句话；你可代笔，风格要配 personality |
| prompt（生图） | 你来写英文提示词：画风 + 构图（upper body）+ 光线；把人物特征词放进去 |
| renderer | 默认 `layered`；用户要 live2d/rive 等 → 说明端上枚举有但**素材产线还没有**，先 layered |

## 规则

- personality / 角色设定属于「最终绑定值」：你的扩写是**建议**，用户点头才算数
  （SOUL Hard Rule 5）。
- 用户提 VRM：直接说明端上 `CharacterEngineType` 枚举里没有 VRM（F-ENGINE-ENUM），
  产线会停在 candidate，指路协调会话的待决 Q2。
- 整理完把 brief 表格念给用户确认，确认后才转 `her-drill` 跑 `new`。
