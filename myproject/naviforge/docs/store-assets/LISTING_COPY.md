# Chrome 网上应用店 — 商品文案（NaviForge）

复制到 [开发者信息中心](https://chrome.google.com/webstore/devconsole) 的 **商品详情**。与扩展 manifest 名称 **NaviForge** 保持一致。

---

## 名称（Name，≤45 字符）

```text
NaviForge
```

可选：

```text
NaviForge — 网页 AI 助手
```

---

## 简短说明（Short description，≤132 字符）

**中文（推荐）**

```text
侧栏 AI + 网页工具箱：读页、总结、截图 OCR、列表提取。自备 API Key，本地会话；⌥N 快捷工具，⌥B 开 Agent。
```

**英文**

```text
Side-panel AI + web toolkit: read, summarize, screenshot OCR, lists. BYOK, local sessions. Alt+N tools, Alt+B Agent.
```

---

## 详细说明（Detailed description）

**中文（完整版，可整段粘贴）**

```text
NaviForge — 把「当前打开的网页」变成可对话、可操作的工作台。

还在复制粘贴、来回切标签？NaviForge 在 Chrome 侧栏里提供一个懂页面的 AI Agent，并附带一整套网页工具（截图、翻译、OCR、JSON 等），让你少点几次鼠标，多完成几件事。

━━━━━━━━━━━━━━━━━━
✦ 核心能力
━━━━━━━━━━━━━━━━━━

【侧栏 Agent】
• 针对「当前标签页」提问：总结文章、解释选中文字、复制正文、按你的目标执行多步任务
• 内置 Skills（页面摩擦、表单、下载、目录爬取等）按需加载，复杂站点更稳
• 支持语音、图片附件；会话与工作区本地保存，可续聊

【网页工具箱 · 控制中心】
• ⌥N：在当前页打开可搜索的快捷工具浮层
• 截图工作室（区域标注 · OCR）、可见/全页截图
• 列表提取、Top N 高亮、就地翻译、视频字幕、文字识别（OCR）
• JSON 格式化、IP 查询等实用小工具

【隐私与掌控】
• 默认 BYOK：使用你自己的 OpenAI 兼容 API（官方 OpenAI、DeepSeek、豆包网关等均可）
• 网络调试、改 Header 等敏感能力默认关闭，可在设置中逐项打开
• 网站访问权限在首次运行 Agent 时按需申请，安装时不授予全站

━━━━━━━━━━━━━━━━━━
✦ 适合谁
━━━━━━━━━━━━━━━━━━

• 研究员 / 运营：快读长文、抓列表、整理信息
• 开发者：看文档、调 JSON、截图标注反馈
• 多标签工作者：侧栏常驻，不离开当前页

━━━━━━━━━━━━━━━━━━
✦ 独立使用
━━━━━━━━━━━━━━━━━━

• 安装扩展即可用，不强制注册、不强制买我们的模型额度
• 可选 NaviForge Host（本地 MCP）需单独安装，不包含在本商店包内

扩展内可能展示非侵入式广告（iframe 托管页），不影响 Agent 核心功能。

━━━━━━━━━━━━━━━━━━
联系与支持
━━━━━━━━━━━━━━━━━━

• 邮箱：justbegin010@gmail.com
• 隐私政策：http://file.ok123find.top/file/privacy_navi.html
• 开源组件说明：http://file.ok123find.top/file/third_party_navi.html
```

**英文（可选）**

```text
NaviForge turns the tab you’re viewing into a conversational, actionable workspace.

Side-panel Agent
• Ask about the active page: summarize, explain selection, copy article text, multi-step tasks
• Skills for paywalls, forms, downloads, catalog workflows
• Voice & image attachments; local sessions

Web toolkit
• Alt+N quick tool palette on the page
• Screenshot studio with OCR, visible/full-page capture
• List extract, translate, subtitles, JSON tools, and more

BYOK by default — your OpenAI-compatible API. Sensitive features off until you enable them in Settings. Broad http(s) access is declared at install for screenshots, in-page tools, and the Agent on user-opened sites.

Works standalone. Optional NaviForge Host is not included in this package.

Non-intrusive ads may appear in extension surfaces via hosted iframe pages.

Contact: justbegin010@gmail.com
Privacy: http://file.ok123find.top/file/privacy_navi.html
Open source: http://file.ok123find.top/file/third_party_navi.html
```

---

## 单一用途（Single purpose）

**中文**

```text
在 Chrome 侧栏提供 AI 智能体与网页工具，用于理解用户当前打开的网页并协助完成用户发起的阅读、对话与自动化任务。
```

**英文**

```text
Provide a side-panel AI agent and web toolkit that understands the active tab and assists with user-directed reading, chat, and automation.
```

---

## Privacy 页 · Permission justification（粘贴到 Chrome 开发者后台）

表单为英文；每项控制在约 2–4 句。向下滚动可能还有 `scripting`、`debugger`、`host` 等字段，一并列出。

### Single purpose description

```text
NaviForge provides a Chrome side-panel AI assistant and in-page web toolkit. It helps users read, chat about, and automate tasks on websites they choose to open—such as summarizing a page, capturing screenshots, extracting lists, or running user-initiated agent workflows. It does not operate outside the user’s browser session or replace unrelated browser features.
```

### activeTab

```text
Used when the user invokes NaviForge on the currently focused tab (extension icon, keyboard shortcut, or context menu) so the extension can capture a visible screenshot or run a one-shot tool before broader host access applies. No background access to inactive tabs via activeTab alone.
```

### identity

```text
Optional OAuth sign-in for users who enable managed API login in Settings (Advanced). chrome.identity.launchWebAuthFlow opens the provider login page and returns tokens only to the extension; BYOK without login is the default and does not use this permission.
```

### tabs

```text
Read and switch tab metadata (URL, title, id) to attach the side-panel Agent, pin the toolkit target tab, open the in-page tool palette, and run screenshots or automation on the tab the user selected. Required for all user-initiated page tools.
```

### tabGroups

```text
Organize multiple tabs opened by agent workflows (e.g., research or parallel subtasks) into Chrome tab groups so users can see related pages together. Only used when the agent or user opens additional tabs as part of a task.
```

### sidePanel

```text
Display the NaviForge Agent chat UI in Chrome’s side panel on the active window so users can converse with the agent while viewing the page.
```

### storage / unlimitedStorage

```text
Store user settings, API profiles (BYOK), session history, and workspace paths locally on the device. unlimitedStorage prevents quota errors for long agent traces and cached tool results; data stays in the user’s browser profile unless they export it.
```

### scripting

```text
Inject content scripts into http(s) pages the user interacts with so the Agent and toolkit can read page structure, click elements, show the ⌥N tool overlay, hide UI chrome during screenshots, and run user-approved automation. Requires host permission on those sites.
```

### debugger

```text
Attach Chrome DevTools Protocol to the active tab only when the user enables Network-related capabilities in Settings → Privacy, to list filtered network events (e.g., media URLs) for user-initiated extraction. Not used when network features are off.
```

### alarms

```text
Schedule lightweight background timers (e.g., Host bridge health checks and session housekeeping) without keeping a persistent busy service worker.
```

### downloads

```text
Save screenshot PNGs and exported files to the user’s Downloads folder when local workspace helper is unavailable or the user chooses browser download fallback.
```

### declarativeNetRequest

```text
Apply optional request-header rewrite rules when the user explicitly enables “Modify headers” in Settings → Privacy. Default is off; rules are user-defined and scoped to debugging/tooling workflows.
```

### contextMenus

```text
Add NaviForge entries to the page right-click menu (open Agent, tool list, workspace) so users can start tools from the page they are viewing.
```

### webNavigation

```text
Detect when the user navigates or reloads a tab so the Agent refreshes page state and can wait for load completion before reading or acting on the page.
```

### cookies

```text
Read cookies only when needed for user-initiated site tooling or session diagnostics on pages the user is working on (e.g., verifying login state described in the privacy policy). Not used for cross-site tracking.
```

### Host permission (`http://*/*`, `https://*/*`)

```text
NaviForge is a general-purpose assistant and screenshot toolkit for arbitrary websites the user opens. Host access is required to inject scripts, capture screenshots, run the in-page tool palette (⌥N), and execute user-directed agent actions on those pages. The extension does not browse sites in the background without user action; all tools are triggered from the side panel, popup, shortcuts, or context menu.
```

---

## 截图上传顺序

| 顺序 | 文件 | 展示内容 |
|------|------|----------|
| 1 | `screenshots/store-1280x800/01-toolkit-quick-menu.jpg` | ⌥N 快捷工具 |
| 2 | `screenshots/store-1280x800/02-agent-sidepanel.jpg` | 侧栏 Agent |
| 3 | `screenshots/store-1280x800/03-toolkit-and-agent.jpg` | ToolKit + Agent |
| 4 | `screenshots/store-1280x800/04-plugins-skills.jpg` | Plugins / Skills |

---

## 广告与合规（内部）

- 仅 **Google AdSense**，**5 个展示单元**：见 [`ads/AD_SLOTS.md`](ads/AD_SLOTS.md)（`NVF-ADS-01` … `05`）。
- 默认 `AD_EMBED_BASE_URL = ''` 不上线广告；接入步骤见 [`LAUNCH_CHECKLIST.md`](../LAUNCH_CHECKLIST.md) **§F**。
- 隐私页已含 Advertising 段落；开通广告后需重新上传 `privacy_navi.html` 并核对 Data safety。
