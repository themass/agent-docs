---
name: web-story-renderer
description: "生成与核心视频配套的 Web Story 页面：同一脚本/日报，HTML 可对外发布；video-pipeline 成功后自动生成。"
version: 1.1.0
author: gqli
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web-story, 网页, 对外发布, 视频配套]
    related_skills: [video-pipeline, video-script-generator, playbook]
---

# Content Studio Web Story Renderer

## 与核心视频的关系

| 产物 | 路径 | 用途 |
|------|------|------|
| **核心成片** | `YYYY-MM-DD-video.mp4` | 小红书/抖音短视频（TTS + 日榜 + 介绍页 + GitHub 滚动） |
| **配套页面** | `assets/YYYY-MM-DD-web-story/index.html` | 可部署到静态站的 Web Story，外链分享 |

二者**共用同一套输入**：

- 日报 `YYYY-MM-DD.md`
- 视频脚本 `YYYY-MM-DD-video-script.md`
- 同一批 GitHub 项目（默认 Top 5）

二者**不是同一条渲染链路**：

- 成片由 `video_generator.py` + ffmpeg 时间轴合成
- 页面由 HTML 模板 + `story-data.json` 渲染，适合浏览器阅读/外链发布

`video-pipeline` / `video-render` **成功后会自动调用本 Skill 生成页面**（只生成 HTML + 预览图，不重复录第二份 mp4）。

## 自动生成（推荐）

```bash
# 跑核心视频时会顺带生成 Web Story 页面
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-06-11
"$HERMES_HOME/scripts/content-studio.sh" video-render 2026-06-11
```

跳过页面生成：

```bash
CONTENT_STUDIO_SKIP_WEB_STORY=1 \
  "$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-06-11
```

## 手动单独生成

```bash
# 仅页面 + 预览图（不录 web-story-video.mp4）
CONTENT_STUDIO_WEB_STORY_SKIP_RECORD=1 \
CONTENT_STUDIO_WEB_STORY_SKIP_AUDIO=1 \
  "$HERMES_HOME/scripts/content-studio-web-story.sh" 2026-06-11

# 实验：额外录一份页面滚动视频（与核心 *-video.mp4 独立）
"$HERMES_HOME/scripts/content-studio-web-story.sh" 2026-06-11
```

## Outputs

```text
reports/YYYY/MM/assets/YYYY-MM-DD-web-story/
  index.html              # 主页面（对外发布）
  styles.css
  story-data.json
  web-story-preview.png
  github/
    owner__repo-fullpage.png
  web-story-video.mp4     # 仅手动开启 --record-video 时
```

## 打开页面

```bash
open reports/YYYY/MM/assets/YYYY-MM-DD-web-story/index.html
```

或本地 HTTP 服务后访问（发布前建议整目录部署）：

```bash
cd reports/YYYY/MM/assets/YYYY-MM-DD-web-story
python3 -m http.server 8765
# http://127.0.0.1:8765/index.html
```

## Rules

- 不修改 `video-pipeline` 的 MP4 生成逻辑；页面是**配套资产**。
- 自动联动时跳过页面录屏，避免与 `*-video.mp4` 重复。
- 页面生成失败**不阻断**已成功的视频成片（警告即可）。
- 复用视频脚本、日报、GitHub 截图 helpers；缺源文件时清晰报错。
