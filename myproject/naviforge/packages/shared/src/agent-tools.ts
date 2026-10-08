/** Single source of truth for model-facing agent tools. Atomic handlers stay as resolver aliases. */
export const AGENT_TOOL_CATALOG = [
  {
    id: 'browser_observe',
    group: 'DOM' as const,
    description:
      '只读感知当前页：snapshot=无障碍快照；read=正文/列表/结构/markdown；extract=列表+媒体；screenshot；pdf；js=MAIN 只读脚本；probe=只读探测',
    args:
      '{ "action": "snapshot"|"read"|"extract"|"screenshot"|"pdf"|"js"|"probe", "mode"?: "compact"|"viewport"|"full"|"body"|"list"|"dom"|"markdown", "n"?: number, "kind"?: "all"|"links"|"buttons"|"feeds", "limit"?: number, "code"?: string, "expression"?: string, "timeout_ms"?: number }',
  },
  {
    id: 'browser_act',
    group: 'DOM' as const,
    description:
      '操作当前页：click/type/press/select/check/hover/drag/upload/scroll/wait/highlight/mark_topn/mark_items/clear_highlights/inject。scroll 只为露出可点元素',
    args:
      '{ "action": "click"|"type"|"press"|"select"|"check"|"hover"|"drag"|"upload"|"scroll"|"wait"|"highlight"|"mark_topn"|"mark_items"|"clear_highlights"|"inject", "index"?: number, "revision"?: number, "selector"?: string, "text"?: string, "key"?: string, "n"?: number, "kind"?: "css"|"html"|"script", "code"?: string }',
  },
  {
    id: 'browser_nav',
    group: 'DOM' as const,
    description: '后退 / 前进 / 刷新 / 打开 URL',
    args: '{ "action": "back"|"forward"|"reload"|"url", "url"?: string }',
  },
  {
    id: 'tabs',
    group: 'Tabs' as const,
    description: '标签：list / switch / close / open（open 后页面工具作用在新标签）',
    args: '{ "action": "list"|"switch"|"close"|"open", "tab_id"?: number, "url"?: string }',
  },
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
      'Host HTTPS GET 拉取静态文本（无 tab、无 cookie）。已知 raw URL 优先；JS 渲染页才 tabs open；媒体/流用 network',
    args: '{ "url"?: string, "urls"?: string[], "max_chars"?: number }',
  },
  {
    id: 'network',
    group: 'Network' as const,
    description: '网络层：read（digest|list|body|media|hls|wait）、intercept、clear。须设置开启。不得 dump cookie/Authorization',
    args:
      '{ "action": "read"|"intercept"|"clear", "mode"?: "digest"|"list"|"body"|"media"|"hls"|"wait", "limit"?: number, "id"?: string, "urlIncludes"?: string, "rules"?: unknown[] }',
  },
  {
    id: 'workspace',
    group: 'System' as const,
    description: '本机工作区 ~/NaviForge（无 rm）。action 含 ls/read/write/… 以及 script_save / script_download',
    args:
      '{ "action": "ls"|"read"|"write"|"mkdir"|"touch"|"stat"|"glob"|"grep"|"script_save"|"script_download", "path"?: string, "content"?: string, "title"?: string, "language"?: string, "filename"?: string, "id"?: string }',
  },
  { id: 'skill_load', group: 'System' as const, description: '按需加载已安装 Skill 的完整正文（渐进披露 L2）', args: '{ "id": string }' },
  {
    id: 'system_spawn_readonly_tasks',
    group: 'System' as const,
    description:
      'Lead 委派 1–3 个只读子 Agent（一次 tool call；内部并行）。subtasks[{title,prompt,urls?,mode:fetch|tab}]。适用：多 URL 并行只读、或 navigation:forbidden 但详情在其它页。父 Agent 必须合并 children[] 后 system_done。',
    args: '{ "subtasks"?: [{ "title": string, "prompt": string, "urls"?: string[], "mode"?: "fetch"|"tab" }], "briefs"?: string[] }',
  },
  { id: 'system_done', group: 'System' as const, description: '结束任务并给出用户可见结论；不要写等待新任务', args: '{ "result": string }' },
  { id: 'system_ask_user', group: 'System' as const, description: '向用户提问', args: '{ "question": string }' },
  { id: 'system_captcha_wait', group: 'System' as const, description: '等待用户完成人机验证', args: '{ "hint"?: string }' },
] as const

export type AgentToolId = (typeof AGENT_TOOL_CATALOG)[number]['id']

export const AGENT_TOOL_IDS = AGENT_TOOL_CATALOG.map((tool) => tool.id) as [
  AgentToolId,
  ...AgentToolId[],
]

/** Atomic / legacy handler id → model-facing catalog id. */
export const HANDLER_TO_MODEL_TOOL: Record<string, AgentToolId> = {
  browser_observe: 'browser_observe',
  browser_act: 'browser_act',
  browser_nav: 'browser_nav',
  tabs: 'tabs',
  network: 'network',
  workspace: 'workspace',
  dom_snapshot: 'browser_observe',
  dom_read: 'browser_observe',
  dom_read_page: 'browser_observe',
  dom_extract_content: 'browser_observe',
  dom_extract_dom: 'browser_observe',
  page_to_markdown: 'browser_observe',
  page_to_pdf: 'browser_observe',
  system_extract_page: 'browser_observe',
  dom_screenshot: 'browser_observe',
  dom_execute_js: 'browser_observe',
  dom_probe: 'browser_observe',
  dom_click: 'browser_act',
  dom_type: 'browser_act',
  dom_press: 'browser_act',
  dom_select: 'browser_act',
  dom_check: 'browser_act',
  dom_hover: 'browser_act',
  dom_drag: 'browser_act',
  dom_upload: 'browser_act',
  dom_scroll: 'browser_act',
  dom_wait: 'browser_act',
  dom_highlight: 'browser_act',
  dom_mark_topn: 'browser_act',
  dom_mark_items: 'browser_act',
  dom_clear_highlights: 'browser_act',
  dom_inject: 'browser_act',
  dom_navigate: 'browser_nav',
  tabs_list: 'tabs',
  tabs_switch: 'tabs',
  tabs_close: 'tabs',
  tabs_open: 'tabs',
  network_read: 'network',
  network_digest: 'network',
  network_list: 'network',
  network_get_body: 'network',
  network_media_hints: 'network',
  network_resolve_hls: 'network',
  network_wait: 'network',
  network_intercept: 'network',
  network_clear_intercepts: 'network',
  workspace_ls: 'workspace',
  workspace_read: 'workspace',
  workspace_write: 'workspace',
  workspace_mkdir: 'workspace',
  workspace_touch: 'workspace',
  workspace_stat: 'workspace',
  workspace_glob: 'workspace',
  workspace_grep: 'workspace',
  script_save: 'workspace',
  script_download: 'workspace',
  skill_load: 'skill_load',
  system_spawn_readonly_tasks: 'system_spawn_readonly_tasks',
  system_done: 'system_done',
  system_ask_user: 'system_ask_user',
  system_captcha_wait: 'system_captcha_wait',
  web_search: 'web_search',
  fetch_text: 'fetch_text',
}

export function canonicalAgentToolId(id: string): string {
  return HANDLER_TO_MODEL_TOOL[id] ?? id
}

export function isCoveredByToolAllowlist(tool: string, allowed: Iterable<string>): boolean {
  const set = allowed instanceof Set ? allowed : new Set(allowed)
  if (set.has(tool)) return true
  const model = HANDLER_TO_MODEL_TOOL[tool]
  return Boolean(model && set.has(model))
}

export function modelFacingToolIds(only?: readonly string[]): AgentToolId[] {
  if (!only?.length) return [...AGENT_TOOL_IDS]
  const want = new Set(only)
  return AGENT_TOOL_IDS.filter((id) => want.has(id))
}

/** Content script and execTurn share this deny string. */
export const INJECT_SCRIPT_DENIED = 'script inject blocked — enable allowDomInject in Settings'
