/** Shared toolkit entries for popup · in-page palette · options panel. */
export type ToolkitCatalogId =
  | 'page-toollist'
  | 'workspace'
  | 'sidepanel'
  | 'studio'
  | 'screenshot'
  | 'fullpage'
  | 'extract'
  | 'mark'
  | 'translate'
  | 'subs'
  | 'genius-fall'
  | 'behavior-forge'
  | 'ocr'
  | 'json'
  | 'myip'
  | 'toolkit-admin'
  | 'settings'
  | 'account'

export type ToolkitCatalogItem = {
  id: ToolkitCatalogId
  label: string
  hint: string
  shortcut?: string
  section: 'quick' | 'capture' | 'page' | 'utility' | 'nav'
  /** Shows footer wait text while running (popup). */
  wait?: boolean
  /** Primary CTA styling in popup. */
  primary?: boolean
}

export const TOOLKIT_CATALOG: ToolkitCatalogItem[] = [
  {
    id: 'sidepanel',
    label: 'Agent 模式',
    hint: '侧栏对话 · 推荐',
    section: 'quick',
    primary: true,
  },
  {
    id: 'account',
    label: '登录 NewAPI',
    hint: '托管 Key · 默认模型',
    section: 'quick',
  },
  {
    id: 'page-toollist',
    label: '快捷工具列表',
    hint: '网页浮层 · 可搜索全部工具',
    shortcut: '⌥N',
    section: 'quick',
  },
  {
    id: 'genius-fall',
    label: '天才陨落',
    hint: '页面悬浮额度监控 · 可拖动',
    section: 'quick',
  },
  {
    id: 'behavior-forge',
    label: '行为回放',
    hint: '打开录制控制台 · DOM + 鼠标轨迹',
    section: 'quick',
  },
  {
    id: 'workspace',
    label: 'Agent 工作台',
    hint: '宽屏对话与任务编排',
    section: 'quick',
  },
  {
    id: 'studio',
    label: '截图工作室',
    hint: '框选 · 标注 · OCR（钉钉式）',
    shortcut: '⌘⇧S',
    section: 'capture',
    wait: true,
  },
  {
    id: 'screenshot',
    label: '可见截图',
    hint: '当前屏幕可见区域',
    shortcut: '⌥A',
    section: 'capture',
    wait: true,
  },
  {
    id: 'fullpage',
    label: '全页截图',
    hint: '滚动拼接长图',
    shortcut: '⌥S',
    section: 'capture',
    wait: true,
  },
  {
    id: 'extract',
    label: '提取列表',
    hint: '归纳列表页重复卡片',
    section: 'page',
  },
  {
    id: 'mark',
    label: '标记 Top N',
    hint: '在页面上高亮前 N 条',
    section: 'page',
  },
  {
    id: 'translate',
    label: '翻译页面',
    hint: '再运行一次还原原文',
    shortcut: '⌥T',
    section: 'page',
  },
  {
    id: 'subs',
    label: '视频字幕',
    hint: '读取字幕轨并贴在画面上',
    section: 'page',
  },
  {
    id: 'ocr',
    label: '识别文字',
    hint: '拖框 OCR 转纯文本',
    section: 'page',
    wait: true,
  },
  {
    id: 'json',
    label: 'JSON 格式化',
    hint: '粘贴 · 修复 · 复制',
    section: 'utility',
  },
  {
    id: 'myip',
    label: 'IP 查询',
    hint: '出口 IP 或任意 IP 详情',
    section: 'utility',
  },
  {
    id: 'toolkit-admin',
    label: '浏览器工具',
    hint: '完整表格 · Header · 结果抽屉',
    section: 'utility',
  },
  {
    id: 'settings',
    label: '控制台',
    hint: '模型 · 自动化 · Sniff',
    section: 'nav',
  },
]

/** Tool list popup order (matches catalog — all tools). */
export const POPUP_TOOL_ORDER: ToolkitCatalogId[] = TOOLKIT_CATALOG.map((item) => item.id)

export const TOOLKIT_SECTION_LABELS: Record<ToolkitCatalogItem['section'], string> = {
  quick: '快捷',
  capture: '截图',
  page: '页面',
  utility: '实用',
  nav: '设置',
}

export function catalogItem(id: ToolkitCatalogId): ToolkitCatalogItem | undefined {
  return TOOLKIT_CATALOG.find((item) => item.id === id)
}

/** Popup i18n keys differ for legacy ids. */
export function popupI18nKey(id: ToolkitCatalogId): string {
  if (id === 'screenshot') return 'visible'
  if (id === 'toolkit-admin') return 'toolkit'
  if (id === 'page-toollist') return 'pageToollist'
  if (id === 'genius-fall') return 'geniusFall'
  if (id === 'behavior-forge') return 'workspace'
  return id
}

export const POPUP_WAIT_KEYS: Partial<Record<ToolkitCatalogId, string>> = {
  studio: 'studioWait',
  screenshot: 'visibleWait',
  fullpage: 'fullpageWait',
  ocr: 'ocrWait',
}
