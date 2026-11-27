# her-production-agent — her 一切资源的生产 agent（M0/M1 数据面先通）

一句话 brief → **persona 角色卡（V2）+ portrait 生图 + 可安装 asset pack +
`ca_her_pack` 演练行**。设计出处：server 仓库
`myproject/companion-agent/docs/hermes-her-production-design-20261128.md`（M0–M4）。

## 组成（Hermes profile 四件套，全部复用官方机制，零自研框架）

| 件 | 作用 |
|---|---|
| `SOUL.md` | 「her 生产协调员」身份 + Hard Rules（脚本是唯一执行通道；只写 sqlite 演练库） |
| `profile.yaml` | profile 描述 |
| `skills/her-drill` | 完整产线工序（new→all→对账→幂等演示） |
| `skills/brief-intake` | 模糊想法 → 结构化 brief（字段缺什么补什么） |
| `scripts/her-production.sh` | **确定性产线本体**：生图（newapi seedream）→ V2 卡装配+`from_v2_json` 校验 → `tools/build_her_pack.py`（G-A 门+upsert+bind）→ 演练库对账 |
| `config.yaml.example` | Hermes 模型通道（newapi 网关；文本 deepseek-v4-1-flash） |
| `.env.example` | 产线环境变量（生图 key、演练库、素材底座） |
| `install.sh` | 幂等装到 `~/.hermes/profiles/her-production`（key 从 coder profile 同步） |

## 跑

```bash
bash hermes/her-production-agent/install.sh        # 装 profile（.env 里补 HER_API_KEY）
S=~/.hermes/profiles/her-production/scripts/her-production.sh
$S new <wd> --name 绮拉 --asset kira-songstress --tagline … --personality …
$S all <wd>                                        # portrait→persona→pack→verify
```

或让 agent 驱动（已验证）：

```bash
hermes -p her-production chat -q "帮我生产一个新的 her：…" --oneshot -Q
```

## 已验证（2026-11-28 本机）

- 脚本链直接跑：`layered-kira-songstress` v1→幂等重跑不动版本（portrait 复用），
  zip 字节 sha256 == `model_ref.hash`。
- **agent 驱动端到端**：模糊一句话 →（agent 整理 brief、命名 asset slug、写生图
  提示词）→ `layered-mo-handjournal` published/manual + 默认绑定 + from_v2_json
  校验过 + 产物 zip 521KB。
- profile 隔离：SOUL/skills 正确加载；agent 拒绝越界（发布/CDN/生产库指路协调会话）。

## 边界与下一步

- 只写 sqlite 演练库；生产 `ca_her_pack` 写入走 publish_release（协调会话）。
- her 包当前随 APK 打包（CDN 落点待定，2026-11-28 裁决）——`--cdn-base` 是占位。
- 引擎枚举 = 端上 `CharacterEngineType`（LAYERED/LIVE2D/RIVE/DUIX/TAO，无 VRM）；
  LIVE2D/RIVE 的素材生成工序属 M2+（marketplace 的 blender MCP / ComfyUI MCP 是候选件）。
