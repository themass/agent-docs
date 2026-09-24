# Browser Toolkit — 工具集分析与集成优先级

## 如何使用（用户）

浏览器工具**不会**操作「工具」这个设置页本身，而是操作你打开的**普通网页标签**（如 bilibili.com、新闻站）。

1. **选网页**：在其它标签打开目标站 → 回到「工具」页 → 点 **选最近打开的网页** 或 **选择网页…** → 看到绿色「已选中」卡片。
2. **运行**：在下方表格点对应工具的 **运行**（步骤 1 完成前按钮为灰色）。
3. **看结果**：截图在「截图预览」并弹出保存；列表在「提取结果」，可导出 JSONL。

**快捷方式**：在目标网页上按 `⌥⇧S`（Option+Shift+S）直接全页截图，无需选标签。

侧栏 Agent 与工具 Tab 是两套入口：Agent 用自然语言自动化；工具 Tab 是一键、无 LLM 的截图/提取/翻译。

---

NaviForge 已有 **43 个 Agent 工具**（DOM / Tabs / Network / System），但大多数只能通过 LLM 循环调用。Browser Toolkit 的目标是：**一键、无 LLM、可预览** 的浏览器操作，与 Agent 共享同一套 DomPlane 实现，避免重复造轮子。

## 现状

| 能力 | 实现层 | Agent 工具 | 手动 UI | 快捷键 |
|------|--------|-----------|---------|--------|
| 可见区域截图 | `dom_screenshot` | ✅ | ❌ | — |
| 全页滚动截图 | `screenshotFullPage()` | ❌ | ❌ | `Alt+Shift+S` ✅ |
| 列表提取 | `dom_extract_content` | ✅ | ❌ | — |
| 页面标记 | `dom_mark_topn` | ✅ | ❌ | — |
| 结构化 DOM | `dom_extract_dom` | ✅ | ❌ | — |
| 合并提取 | `system_extract_page` | ✅ | ❌ | — |
| 页面翻译 | — | ❌ | ❌ | — |
| 抓取脚本导出 | `script_save` + extract | 部分 | ❌ | — |
| 打开工具面板 | — | — | ❌ | `Alt+Shift+N`（声明未接线） |

**核心差距**：能力在 runtime 里，用户无法在不跑 Agent 的情况下使用；`open-toolkit` 与工具 Tab 未落地。

---

## 工具集候选（按价值 × 实现成本）

### P0 — 值得立即集成（复用现有实现）

| 工具 | 价值 | 成本 | 集成方式 |
|------|------|------|----------|
| **全页截图** | 运维/设计/取证高频需求 | 低（已实现 runner） | 工具 Tab 按钮 + 预览/下载；保留 `Alt+Shift+S` |
| **可见截图** | 快速分享当前视口 | 极低 | `dom_screenshot` 一键调用 |
| **列表提取 Top N** | 与 live 测试、B 站 top3 同路径 | 低 | `dom_extract_content` + 结果列表 + JSONL 导出 |
| **标记 Top N** | 可视化验证提取结果 | 低 | `dom_mark_topn` |
| **打开工具面板** | 快捷键入口 | 极低 | `open-toolkit` → sidePanel + 导航到工具 Tab |
| **Google 翻译** | 用户明确需求；零 API 成本 | 低 | 新标签打开 `translate.google.com/translate?u=…` |

### P1 — 值得集成（需少量新代码）

| 工具 | 价值 | 成本 | 说明 |
|------|------|------|------|
| **双语对照翻译** | 不离开当前页 | 中 | Cloud Translation API + TreeWalker 映射 + `data-naviforge-i18n` 还原 |
| **页面 Markdown 导出** | 笔记/归档 | 低 | 包装 `system_extract_page` 或 Readability 式正文抽取 |
| **网络摘要卡片** | 调试 API/媒体站 | 低 | 展示 `network_digest` 最近 N 条，一键复制 |
| **元素拾取器** | 写 Playbook / 调试 selector | 低 | 已有 `pick_element`，暴露到工具 Tab |
| **dom_screenshot_full 进 Agent catalog** | Agent 可主动长页截图 | 低 | 加 catalog 条目 + execTurn 分支 |

### P2 — 有条件集成（垂直场景）

| 工具 | 价值 | 成本 | 说明 |
|------|------|------|------|
| **影视站抓取 MVP** | 频道/分页/播放 URL | 中高 | `EvidenceBundle` → JSONL；HITL 确认后 `script_save` |
| **分页遍历** | 多页列表 | 中 | 与 grabber 绑定；需 URL 模板或「下一页」探测 |
| **PDF 导出** | 报告归档 | 中 | html2canvas + jsPDF 或打印 API |
| **Accessibility 快照** | 无障碍审计 | 中 | axe-core 注入（体积与 CSP 风险） |
| **录屏/GIF** | 演示回放 | 高 | `chrome.tabCapture` 或 offscreen document |

### P3 — 暂不集成或外包

| 工具 | 原因 |
|------|------|
| 完整爬虫框架 | 与 Agent + Playbook 职责重叠；维护成本高 |
| 内置 LLM 翻译 | 成本高、质量不稳；Google 标签页足够 P0 |
| CDP 全功能面板 | 与 network debugger 冲突；已有 `chrome.debugger` 路径 |
| 密码/表单自动填充 | 安全与合规风险 |
| 广告拦截 | 非核心；商店审核敏感 |

---

## 架构原则

```
用户点击工具 Tab / 快捷键
        ↓
toolkit-actions.ts（薄封装）
        ↓
createChromeDomPlane(tabId)  ← 与 Agent 相同
        ↓
content script PAGE_CONTROL
```

- **不新增 Agent 工具**除非需要 LLM 主动调用（如 `dom_screenshot_full`）。
- **敏感能力**（`dom_inject`、`network_intercept`）不进工具 Tab，留在设置 + Agent。
- **翻译 P0** 用导航到 Google；P1 再做页内 overlay。

### 与 Agent 的边界

| 场景 | 推荐路径 |
|------|----------|
| 「帮我找出 B 站 top3」 | Agent + skill |
| 「截一张整页图」 | 工具 Tab / `Alt+Shift+S` |
| 「把这个列表导出 JSONL」 | 工具 Tab 提取 + 导出 |
| 「分析这个电影站并生成抓取脚本」 | Agent + grabber skill（P2） |

---

## 推荐路线图

1. **现在（P0）**：工具 Tab — 截图、提取、标记、翻译、JSONL 导出；`Alt+Shift+N` 打开面板。
2. **下一迭代（P1）**：页内翻译 overlay、Markdown 导出、`dom_screenshot_full` 进 catalog。
3. **垂直 MVP（P2）**：影视站 JSONL + 单页 pagination 探测 + `Alt+Shift+G` 触发 Agent grabber 模板。

---

## 快捷键规划

| 快捷键 | 动作 | 状态 |
|--------|------|------|
| `Alt+Shift+N` | 打开工具面板 | P0 |
| `Alt+Shift+S` | 全页截图并下载 | ✅ |
| `Alt+Shift+T` | 翻译当前页（Google） | P1 |
| `Alt+Shift+G` | 打开抓取助手（Agent 预填任务） | P2 |
| `Alt+Shift+E` | 提取 Top 10 并复制 JSONL | P1 |

---

## 参考文件

- `packages/shared/src/agent-tools.ts` — 工具目录 SSOT
- `apps/extension/src/lib/chrome-dom-plane.ts` — DomPlane 实现
- `apps/extension/src/lib/capture-full-page*.ts` — 全页截图
- `apps/extension/src/lib/content-extract.ts` — 列表归纳提取
- `apps/extension/src/entrypoints/options/toolkit-panel.tsx` — 工具 Tab UI
