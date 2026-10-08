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

BYOK by default — your OpenAI-compatible API. Sensitive features off until you enable them in Settings. Site access requested on first Agent run, not at install.

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
