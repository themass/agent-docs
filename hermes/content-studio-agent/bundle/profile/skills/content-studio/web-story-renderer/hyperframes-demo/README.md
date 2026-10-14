# Web Story × HyperFrames Demo

把 Content Studio Web Story 做成可 seek 的 HTML composition，再用 HyperFrames 渲染竖屏 MP4。

## 已渲染样片

- `web-story-demo.mp4` — 14s · 1080×1920 · ~4MB（draft）
- 打开：`open web-story-demo.mp4`

时间轴：

| 段 | 时间 | 内容 |
|----|------|------|
| Hero | 0–3.5s | 主题 + Top 2 |
| Project | 3.5–9s | rea 介绍 + GitHub 截图滚动（GSAP） |
| Summary | 9–14s | 趋势 / 机会 / 行动 |

## 重新渲染

```bash
cd "$(dirname "$0")"
export PUPPETEER_SKIP_DOWNLOAD=1
export HYPERFRAMES_BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
npm install hyperframes --registry=https://registry.npmmirror.com --no-fund --no-audit
npx hyperframes lint
npx hyperframes render . -o web-story-demo.mp4 -q draft -w 1 --fps 30 --low-memory-mode
```

需要：Node.js 22+、FFmpeg、本机 Chrome（或 `npx hyperframes browser ensure`）。

## 和现有 Web Story 的关系

- 静态页 `../templates/index.html` 继续用于浏览器阅读 / 外链。
- 本目录是「HTML → 确定性视频」实验：动画必须可 seek（GSAP timeline / 有限 keyframes），不能用 `animation: infinite`。
- 下一步可把 `story-data.json` 自动灌进 composition，并接入 `content-studio.sh`。
