---
name: hybrid-video
description: "Content Studio 第三条视频链路：基于分镜的相关素材视频。保留 sop/mpt 现有链路，新增 GitHub 证据 + 概念卡 + 可选 Seedance AI b-roll 的 hybrid 视频。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [视频, hybrid, Seedance, 分镜, AI素材]
    related_skills: [video-execution, video-script-generator, storyboard-planner, video-pipeline, moneyprinter-video]
---

# Hybrid Video Pipeline

`hybrid-video` 是 Content Studio 的**第三条视频链路**。它不替换现有的 `sop视频` 和 `mpt视频`，而是在两者之外新增一条「分镜驱动的相关素材视频」链路。

## Positioning

| 链路 | 触发 | 产物 | 作用 |
|------|------|------|------|
| sop 视频 | `生成 sop视频` | `*-video.mp4` | 主视频：GitHub 页面滚动、项目证据、日榜开场。 |
| mpt 视频 | `生成 mpt视频` | `*-mpt-video.mp4` | 快速样片：口播 + 通用库存素材 + 字幕。 |
| hybrid 视频 | `生成 hybrid视频` | `*-hybrid-video.mp4` | 新链路：GitHub 证据 + 概念卡 + 2-3 段相关 AI 素材。 |

## Hard Rules

1. **只新增，不替换**：不得改变 `video-pipeline`、`video-mpt`、`video-mpt-pipeline` 的行为。
2. **独立命名**：所有产物必须使用 `*-hybrid-*` 或 `assets/*-hybrid/`，不得覆盖 `*-video.mp4` 或 `*-mpt-video.mp4`。
3. **必须用 terminal 执行**：Chat 触发时必须通过 `terminal` 执行 `content-studio.sh video-hybrid-pipeline [DATE]`，禁止使用 `execute_code` 跑长视频任务。
4. **AI 素材可降级**：Seedance 未配置、失败或超时时，默认降级为相关概念卡，不阻塞 v1 pipeline。
5. **GitHub 证据不降级为泛素材**：项目证据段必须保留 `github` 类型或明确标记为占位，不允许悄悄换成 generic coding stock video。
6. **AI 段限制**：中期版本每条视频最多 2-3 个 `ai_broll` 段，避免成本和风格失控。

## Commands

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"

# 只看 hybrid 状态
"$HERMES_HOME/scripts/content-studio.sh" hybrid-status
"$HERMES_HOME/scripts/content-studio.sh" hybrid-status 2026-06-13

# 已有脚本时：生成 spec/assets，尽量渲染 hybrid 视频
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid 2026-06-13

# 完整链路：如脚本不存在，先提示用户生成脚本；v1 不覆盖旧脚本
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline
"$HERMES_HOME/scripts/content-studio.sh" video-hybrid-pipeline 2026-06-13
```

## Production Flow

```text
reports/YYYY/MM/YYYY-MM-DD-video-script.md
  │
  ▼
hybrid_spec.py
  ├─ YYYY-MM-DD-hybrid-storyboard.md
  └─ YYYY-MM-DD-hybrid-production-spec.yaml
  │
  ▼
hybrid_assets.py
  ├─ cards/*.png
  ├─ ai-broll/*.mp4 or fallback-card png
  ├─ github/*.txt placeholder in v1
  └─ clips/*.mp4
  │
  ▼
hybrid_compositor.py
  ├─ tries to compose clips with ffmpeg
  └─ outputs YYYY-MM-DD-hybrid-video.mp4 when enough clips exist
```

## Spec Contract

Hybrid uses its own spec file:

```text
reports/YYYY/MM/YYYY-MM-DD-hybrid-production-spec.yaml
```

Required segment fields:

```yaml
- id: intro-ai-broll
  asset_type: ai_broll
  visual_type: ai_generated
  duration_seconds: 6
  narration_ref: intro_metaphor
  visual_prompt: "English prompt tied to the thesis."
  negative_prompt: "watermark, logo, blurry, unreadable text"
  ai_broll:
    provider: volcengine_seedance
    mode: text_to_video
    fallback: concept_card
```

Supported `asset_type`:

- `card` — concept/project/summary card.
- `github` — repository evidence segment or v1 placeholder.
- `ai_broll` — Seedance-generated related material, with card fallback.
- `ranking` — daily ranking proof, future v2.
- `transition` — future v2.

## Seedance

Seedance integration is provider-isolated in `scripts/seedance_client.py`.

Expected environment variables:

```bash
VOLCENGINE_ACCESS_KEY_ID=...
VOLCENGINE_SECRET_ACCESS_KEY=...
VOLCENGINE_REGION=cn-beijing
VOLCENGINE_SEEDANCE_MODEL=<copy-from-volcengine-console>
HYBRID_AI_PROVIDER=volcengine_seedance
```

If credentials are missing, the pipeline must continue with fallback cards and explain that in `hybrid-status`.

## Hermes Response Rules

After running a hybrid command, respond with:

```markdown
## Hybrid 视频进度 — {DATE}

| 阶段 | 状态 | 产出 |
|------|------|------|
| Spec | ✅/❌ | `...-hybrid-production-spec.yaml` |
| Assets | ✅/❌ | `assets/...-hybrid/` |
| AI B-roll | ✅/fallback/❌ | Seedance or fallback card |
| Video | ✅/待合成 | `...-hybrid-video.mp4` |

说明：sop/mpt 现有链路未变；hybrid 是第三条独立链路。
```
