# test-site 集成场景

本地启动：`npm run demo:site` → http://localhost:4177

## Phase 0 — 基础 DOM

1. 任务：`在测试页输入 hello 并点击 Go，确认结果出现 Success`
2. 预期：Run success，Playbook 锻造 2 步（type + click）

## Phase C — iframe / shadow

1. 任务：`点击 iframe 内 Frame Go 按钮，确认出现 Frame Success`
2. 预期：snapshot 的 `FRAMES` 段含 `[frame f0]`；click 使用 `framePath: "f0"`

3. 任务：`找出 shadow 内 Demo Video 1 链接文本`
4. 预期：`FRAMES` 或 snapshot 可见 shadow 补充行

## Phase C — 稳定等待

1. 点击 Go 后立即：`dom_wait kind=stable`
2. 预期：MutationObserver 安静窗口后返回 ok

## Network — media_hints

在控制台执行 `fetch('/fake/master.m3u8')` 后，Agent 使用 `network_media_hints` 应包含 hls 条目。

## Network — body 捕获

设置 → 隐私 → 手动开启 **捕获 Network 响应体预览**（默认关，≤32KB）。
仅 JSON/文本（含 m3u8 文本）；mp4/ts 等二进制不会保存。

## Network — media hints

访问 `/fake/master.m3u8` 后 `network_media_hints` 应包含 hls 条目（URL 级别，不展开 segment 列表）。

## extract + API

`GET /fake/api/videos.json` + `system_extract_page` 应合并出 Demo Video 1/2。
