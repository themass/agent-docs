---
name: her-drill
description: 把一句「她是谁 / 长什么样」的意图跑成一条完整 her 三件套：V2 persona 角色卡 + portrait 生图 + 可安装 asset pack + ca_her_pack 演练行。唯一执行通道是 scripts/her-production.sh。
version: 0.1.0
author: hermes-her-production (drill)
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [her, production, drill, companion]
---

# her-drill —— 一键把 brief 跑成可安装的 her

## 前置

- `scripts/her-production.sh` 可执行（`chmod +x`），profile home 下有 `.env`
  （`HER_API_KEY` 已填）。缺任何一样 → 先对用户说清楚缺什么，别硬跑。
- 产出目录统一用 `<profile home>/runs/<asset-slug>-<yyyymmdd>/`（绝对路径）。

## 步骤（顺序固定，每步看 `✅` 才进下一步）

1. **brief 整理**（你的自由区）：把用户的话提炼成
   `--name`（中文可）`--asset`（拉丁 slug，= pack_id）`--tagline` `--personality`
   `--first-mes` `--prompt`（生图提示词，英文出图质量稳）。
   中文名必须给 `--asset`——pack_id 不吃中文，脚本会拒。
   跑：`scripts/her-production.sh new <workdir> --name … --asset … --tagline … --personality … --first-mes … --prompt …`
2. **一条龙**：`scripts/her-production.sh all <workdir>`
   （portrait → persona 校验 → pack+deploy → verify 对账）。
3. **对账复述**：把 verify 打印的 `her_id / pack_version / status / model_ref.hash /
   bound_default` 原样转述给用户，命名以脚本输出为准（`<renderer>-<asset>`）。
4. **重跑幂等演示**（可选但推荐）：再跑一次 `all`，确认 `pack_version` 不动——
   这是给用户的「产线可重复」证据。

## 失败处理

- 任何一步非 0：贴 terminal 最后 30 行 + 你的归因（key 没配 / 素材 zip 不在 /
  G-A 契约门拒了 / 卡校验没过），给出下一步建议。**不得只说「失败了」。**
- G-A 门拒包 ≠ 你写错了：是产物不符合端上契约（`CharacterAssetPolicy` 镜像），
  把 violation 原文贴出来，指到 `tools/build_her_pack.py` 的契约注释。

## 边界

- 这只写 sqlite 演练库。用户要「发到生产 / 上 CDN / 装到 App」→ 指路协调会话
  （publish_release 链），你不执行。
- 最终绑定值（role 绑定、CDN 落点、许可声明）由人确认——你出建议，不出结论。
