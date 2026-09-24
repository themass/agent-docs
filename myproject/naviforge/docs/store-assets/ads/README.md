# 扩展内广告（iframe 方案）

Chrome MV3 **禁止**在 `extension_pages` 的 CSP 里加载 `pagead2.googlesyndication.com`，否则扩展无法加载（manifest 报错）。

## 做法

1. 把本目录 `agent.html`、`options.html`、`screenshot.html` 部署到你的服务器（可内嵌 AdSense）。
2. 在扩展里设置：

```ts
// apps/extension/src/lib/ads-config.ts
export const AD_EMBED_BASE_URL = 'http://file.ok123find.top/file/ads'
```

3. 重新 `npm run build`，加载 `dist/chrome-mv3`。

扩展用 **iframe** 嵌入上述页面；AdSense 脚本跑在你的网页上，不违反 MV3 CSP。

## 注意

- 页面需允许被 iframe 嵌入（不要 `X-Frame-Options: DENY`）。
- HTTPS 站点优先；`frame-src` 已允许 `http:` / `https:`。
