/** Single source of truth for agent tool names, prompt docs, and UI catalog. */
export const AGENT_TOOL_CATALOG = [
  { id: 'dom_click', group: 'DOM' as const, description: '点击页面元素', args: '{ "index"?: number, "revision": number, "framePath"?: string, "selector"?: string }' },
  { id: 'dom_type', group: 'DOM' as const, description: '向输入框键入文本', args: '{ "index"?: number, "text": string, "revision": number, "selector"?: string }' },
  { id: 'dom_snapshot', group: 'DOM' as const, description: '重新抓取可访问性快照', args: '{ "mode"?: "compact"|"viewport"|"full" }' },
  {
    id: 'dom_read',
    group: 'DOM' as const,
    description: '读页统一入口：body=正文；list=列表(n)；dom=链接/按钮结构；markdown=写入 pages/',
    args: '{ "mode": "body"|"list"|"dom"|"markdown", "n"?: number, "kind"?: "all"|"links"|"buttons"|"feeds", "limit"?: number }',
  },
  {
    id: 'page_to_pdf',
    group: 'DOM' as const,
    description: '将当前页打印为 PDF 并写入工作区 pages/，返回 path',
    args: '{}',
  },
  { id: 'dom_highlight', group: 'DOM' as const, description: '滚动跟随高亮标记', args: '{ "targets": [{ "index"?: number, "selector"?: string, "label": string, "color"?: string }], "revision"?: number }' },
  { id: 'dom_mark_topn', group: 'DOM' as const, description: '标记当前可见列表前 N 项（自动识别重复卡片结构，TOP1..TOPn）', args: '{ "n"?: number }' },
  { id: 'dom_mark_items', group: 'DOM' as const, description: '标记 dom_read list 返回的记录（仅在用户要求标记时使用）', args: '{ "items": [{ "index": number, "label"?: string, "detail"?: string }] }' },
  { id: 'dom_clear_highlights', group: 'DOM' as const, description: '清除高亮', args: '{}' },
  { id: 'dom_inject', group: 'DOM' as const, description: '注入 css/html（script 另需隐私开关）', args: '{ "kind": "css"|"html"|"script", "code": string }' },
  { id: 'dom_execute_js', group: 'DOM' as const, description: '在页面 MAIN 世界执行只读 JS（fetch / querySelectorAll），返回 JSON 摘要。不要用它改 DOM', args: '{ "code": string, "timeout_ms"?: number }' },
  { id: 'dom_navigate', group: 'DOM' as const, description: '后退 / 前进 / 刷新 / 打开 URL', args: '{ "action": "back"|"forward"|"reload"|"url", "url"?: string }' },
  { id: 'dom_scroll', group: 'DOM' as const, description: '滚动以露出可点元素，不要用来收割全文', args: '{ "to"?: "top"|"bottom"|"y", "y"?: number, "direction"?: "up"|"down", "amount"?: number }' },
  { id: 'dom_wait', group: 'DOM' as const, description: '等待页面稳定、文本或 Chrome 下载完成', args: '{ "kind": "stable"|"text"|"network_idle"|"download", "text"?: string, "timeout_ms"?: number }' },
  { id: 'dom_press', group: 'DOM' as const, description: '发送键盘按键（Enter/Escape/Tab/组合键）', args: '{ "key": string, "modifiers"?: string[] }' },
  { id: 'dom_select', group: 'DOM' as const, description: '选择下拉框选项', args: '{ "index": number, "value": string, "revision": number }' },
  { id: 'dom_check', group: 'DOM' as const, description: '勾选/取消 checkbox 或 radio', args: '{ "index": number, "checked": boolean, "revision": number }' },
  { id: 'dom_upload', group: 'DOM' as const, description: '向 file input 上传 base64 文件', args: '{ "index": number, "filename": string, "content_base64": string, "revision": number }' },
  { id: 'dom_hover', group: 'DOM' as const, description: '悬停触发菜单/tooltip', args: '{ "index": number, "revision": number }' },
  { id: 'dom_drag', group: 'DOM' as const, description: '拖拽元素到另一元素', args: '{ "from_index": number, "to_index": number, "revision": number }' },
  { id: 'dom_screenshot', group: 'DOM' as const, description: '截取可见区域截图', args: '{}' },
  { id: 'dom_probe', group: 'DOM' as const, description: 'MAIN world 只读探测（需隐私开关）', args: '{ "expression": string }' },
  { id: 'tabs_list', group: 'Tabs' as const, description: '列出当前窗口标签页', args: '{}' },
  { id: 'tabs_switch', group: 'Tabs' as const, description: '切换到指定标签页', args: '{ "tab_id": number }' },
  { id: 'tabs_close', group: 'Tabs' as const, description: '关闭标签页', args: '{ "tab_id": number }' },
  { id: 'tabs_open', group: 'Tabs' as const, description: '打开新标签并切过去。当前无网页、chrome://、或任务需要该 URL 时使用；之后的页面工具作用在新标签', args: '{ "url": string }' },
  {
    id: 'web_search',
    group: 'Web' as const,
    description: '外网检索，返回标题/链接/摘要。同类、竞品、未知 URL 时先用；不是当前页搜索框',
    args: '{ "query": string, "n"?: number }',
  },
  {
    id: 'fetch_text',
    group: 'Web' as const,
    description:
      'Host HTTPS GET 拉取静态文本（无 tab、无 cookie）。已知 raw URL（raw.githubusercontent.com、api.github.com JSON 等）优先于 tabs_open/dom_read；JS 渲染页才开 tab；媒体/流用 network_read',
    args: '{ "url"?: string, "urls"?: string[], "max_chars"?: number }',
  },
  { id: 'script_save', group: 'System' as const, description: '保存可复用 Python/Shell/JS 脚本', args: '{ "title": string, "language": "python"|"shell"|"javascript", "filename": string, "content": string }' },
  { id: 'script_download', group: 'System' as const, description: '下载已保存脚本', args: '{ "id": string }' },
  {
    id: 'workspace',
    group: 'System' as const,
    description: '本机工作区 ~/NaviForge（路径相对根目录；无 rm）',
    args:
      '{ "action": "ls"|"read"|"write"|"mkdir"|"touch"|"stat"|"glob"|"grep", "path"?: string, "content"?: string, "pattern"?: string, "glob"?: string }',
  },
  { id: 'skill_load', group: 'System' as const, description: '按需加载已安装 Skill 的完整正文（渐进披露 L2）', args: '{ "id": string }' },
  {
    id: 'network_read',
    group: 'Network' as const,
    description: '读取已捕获网络：digest|list|body|media|hls|wait',
    args:
      '{ "mode": "digest"|"list"|"body"|"media"|"hls"|"wait", "limit"?: number, "id"?: string, "urlIncludes"?: string, "method"?: string, "urlRegex"?: string, "status"?: number, "timeout_ms"?: number, "text"?: string, "baseUrl"?: string }',
  },
  { id: 'network_intercept', group: 'Network' as const, description: '拦截/mock/转发', args: '{ "rules": [...] }' },
  { id: 'network_clear_intercepts', group: 'Network' as const, description: '清除拦截规则', args: '{}' },
  { id: 'system_done', group: 'System' as const, description: '结束任务并给出用户可见结论；不要写等待新任务', args: '{ "result": string }' },
  { id: 'system_ask_user', group: 'System' as const, description: '向用户提问', args: '{ "question": string }' },
  {
    id: 'system_spawn_readonly_tasks',
    group: 'System' as const,
    description:
      'Lead→Worker delegation: spawn 1–3 parallel readonly child agents (one tool call; ephemeral tabs; isolated trace). Prefer subtasks[{title,prompt,urls?,mode}] (DeerFlow-style); legacy briefs[] ok. Children: fetch_text / tabs_open+dom_read / network_read / web_search / readonly MCP / system_done — no writes, no nested spawn. USE when 2+ independent read-only URLs/pages or parent navigation:forbidden but detail pages hold data. Parallel: pack ≤3 per call; >3 → multiple spawn rounds, merge children[] before system_done. DO NOT USE: single URL (parent fetch_text/dom_read), sequential dependency without prior batch, writes/HITL. Parent must synthesize final answer from children[], not dump raw logs.',
    args:
      '{ "subtasks"?: [{ "title": string, "prompt": string, "urls"?: string[], "mode"?: "fetch"|"tab" }], "briefs"?: string[] }',
  },
  { id: 'system_extract_page', group: 'System' as const, description: '从 snapshot+network 提取列表/媒体', args: '{}' },
  { id: 'system_captcha_wait', group: 'System' as const, description: '等待用户完成人机验证', args: '{ "hint"?: string }' },
] as const

export type AgentToolId = (typeof AGENT_TOOL_CATALOG)[number]['id']

export const AGENT_TOOL_IDS = AGENT_TOOL_CATALOG.map((tool) => tool.id) as [
  AgentToolId,
  ...AgentToolId[],
]

export function canonicalAgentToolId(id: string): string {
  return id
}

/** Builtin ids exposed in model `tools[]`. */
export function modelFacingToolIds(only?: readonly string[]): AgentToolId[] {
  if (!only?.length) return [...AGENT_TOOL_IDS]
  const want = new Set(only)
  return AGENT_TOOL_IDS.filter((id) => want.has(id))
}

/** Content script and execTurn share this deny string. */
export const INJECT_SCRIPT_DENIED = 'script inject blocked — enable allowDomInject in Settings'
