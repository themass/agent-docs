---
name: storyboard-planner
description: "把趋势分析脚本转成视频分镜和生产规范。"
version: 1.0.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [视频, 分镜, production-spec, GitHub]
    related_skills: [video-script-generator, video-pipeline]
---

# GitHub 视频分镜规划器

本 Skill 把 `video-script-generator` 产出的趋势分析脚本转成可执行的分镜和 `production-spec.yaml`。它负责让画面服务观点，而不是让视频生成器临时猜测该用什么素材。

## When to Use

使用本 Skill：

- 已经有 `*-video-script.md`，需要生成 `*-storyboard.md`。
- 需要把口播拆成画面段落、转场、红框标注和概念卡。
- 需要生成给 `video-pipeline` 执行的 `*-production-spec.yaml`。

不要用它生成口播脚本；脚本生成归 `video-script-generator`。

## Inputs

- `*-video-script.md`：必须包含 `## 本期主题`、`## 入选项目`、`## 完整口播文本`。
- 当日日报或周报：用于确认项目排名、描述和数据。
- 可选：用户指定的视频风格、时长、重点项目。

## Outputs

默认输出到脚本同目录：

```text
YYYY-MM-DD-storyboard.md
YYYY-MM-DD-production-spec.yaml
```

若脚本文件名是 `YYYY-MM-DD-video-script.md`，输出：

```text
YYYY-MM-DD-storyboard.md
YYYY-MM-DD-production-spec.yaml
```

## Visual Vocabulary

支持以下画面类型：

| 类型 | 用途 | 规则 |
|------|------|------|
| `ranking_chart` | 开场证明来自真实热榜 | 只放在开场或封面 |
| `concept_card` | 解释 thesis、类比、能力列表 | 适合观点和抽象概念 |
| `github_scroll_callout` | 展示真实 GitHub 仓库和红框 | 每个项目至少一次 |
| `workflow_diagram` | 展示系统链路、部署流程 | 适合集成闭环 |
| `comparison_card` | 对比旧方式和新方式 | 适合行业转折 |
| `summary_card` | 收尾长期判断 | 只放在结尾 |
| `demo_clip` | README GIF 或产品 Demo | 仅当项目确有演示素材 |
| `transition` | 段间转场 | 不承载口播，0.3-0.6 秒 |

## Procedure

### Step 1 — 提取脚本结构

读取脚本中的：

- `## 本期主题`
- `## 入选项目`
- `## 完整口播文本`
- `## 分镜表`（若已有，先校正再输出）

### Step 2 — 切分口播段落

将口播拆成：

1. `intro-thesis`
2. `intro-ranking`（可选）
3. 每个项目的 `project-N-scroll`
4. 每个项目的 `project-N-card` 或 `project-N-diagram`
5. `outro-vision`

切分原则：

- 开场 thesis 用概念卡。
- 热榜数据用排行图。
- 每个项目必须有 GitHub 滚动红框。
- 抽象机制用概念卡或流程图。
- 结尾长期判断用总结卡。

### Step 3 — 设计画面与转场

每个项目推荐结构：

```text
github_scroll_callout 18-25s
transition 0.3-0.6s
concept_card / workflow_diagram 5-8s
transition 0.3-0.6s
```

如果项目是 UI/Demo 类，可插入 `demo_clip`，但不能替代 `github_scroll_callout`。

### Step 4 — 写 `storyboard.md`

按 `templates/storyboard.md` 输出：

- 视频目标。
- 分镜表。
- 画面说明。
- 红框标注重点。
- 风险与缺失素材。

### Step 5 — 写 `production-spec.yaml`

按 `templates/production-spec.yaml` 输出结构化规范。它是渲染器未来的稳定输入。

## Quality Gates

输出前检查：

- 每个入选项目至少一个 `github_scroll_callout`。
- 开场有 thesis 画面，不是直接滚仓库。
- 至少一个概念卡解释行业判断。
- 结尾有 `summary_card`。
- 转场不喧宾夺主。
- 所有 repo 均来自脚本 `## 入选项目`。
- 没有把画面类型写成无法执行的自由文本。

## Pitfalls

- 不要把分镜写成「配一些截图」。
- 不要让所有项目都只有 GitHub 滚动。
- 不要为了炫酷使用与项目能力无关的 AI 生图。
- 不要把 `demo_clip` 当默认能力；只有明确存在 Demo 素材时才用。
- 不要把脚本策略塞进 shell 参数。

## Verification

完成后确认：

- `*-storyboard.md` 存在。
- `*-production-spec.yaml` 存在。
- spec 中 `segments` 至少包含 intro、3 个 project scroll、outro。
- 所有 `repo` 字段都是 `owner/repo` 格式。
- 每个 project 的 `visual_type` 可由 `video-pipeline` 识别。
