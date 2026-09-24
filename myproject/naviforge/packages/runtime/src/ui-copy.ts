/** User-visible runtime copy. UI chrome lives in the extension catalogs.
 *  Adding a language: append UI_LOCALES + a Copy block here (runtime cannot import the extension).
 */

export const UI_LOCALES = ['en', 'zh-CN', 'es'] as const
export type UiLocale = (typeof UI_LOCALES)[number]

export function resolveUiLocale(raw?: string): UiLocale {
  return raw === 'zh-CN' || raw === 'es' ? raw : 'en'
}

type Copy = {
  acting: string
  actingSkill: string
  actingMcp: string
  actingAsk: string
  actingDone: string
  actingSearch: string
  actingSearchEmpty: string
  actingSub: string
  actingTool: string
  timeout: string
  tokenBudget: string
  privacy: Record<string, string>
  hardDeny: string
  hardDenySearch: string
  sameFailureNav: string
  sameFailure: string
  transportAsk: string
  actionLoop: string
}

const en: Copy = {
  acting: 'Working…',
  actingSkill: 'Loading skill: {id}',
  actingMcp: 'Calling MCP: {tool}',
  actingAsk: 'Waiting for you…',
  actingDone: 'Finishing…',
  actingSearch: 'Searching: {query}',
  actingSearchEmpty: 'Searching…',
  actingSub: 'Starting a read-only subtask…',
  actingTool: 'Running {tool}',
  timeout: 'Run hit the {minutes}-minute wall-clock limit and stopped.',
  tokenBudget: 'Run reached the token budget {budget} (used {used}) and stopped.',
  privacy: {
    inject_denied: 'Settings → Privacy → Allow DOM script inject (save to apply)',
    execute_js_denied: 'Settings → Privacy → Allow DOM script inject (save to apply)',
    probe_denied: 'Settings → Privacy → Allow MAIN-world read-only probe (save to apply)',
    intercept_denied: 'Settings → Privacy → Allow network intercept (save to apply)',
    no_body: 'Settings → Privacy → Capture network response-body previews (save to apply)',
    attach_failed: 'Close DevTools / other debug extensions on this tab, then retry',
    no_network: 'Side panel: enable Network plane',
    no_search_key: 'Settings → Models → Web search (Brave / Tavily)',
    shot_not_saved: 'Settings → Workspace → start the local helper (shots write to ~/NaviForge/shots)',
    page_not_saved: 'Settings → Workspace → start the local helper (exports write to ~/NaviForge/pages)',
    no_workspace: 'Settings → Workspace → connect the local helper',
  },
  hardDeny:
    'Tool {tool} was blocked by settings ({code}). Turn it on under {where}, then reply Continue — or Stop to end. Do not retry the same denied tool.',
  hardDenySearch:
    'Tool {tool} needs a search API key ({code}). Add it under {where}, then reply Continue — or Stop to end. Do not scrape Google results instead.',
  sameFailureNav:
    'dom_navigate failed {count} times: missing action/url. Use {"action":"url","url":"https://..."} or click a list item. Empty {{}} is forbidden. Reply Continue to change strategy, or Stop to end.',
  sameFailure:
    'Tool {tool} failed {count} times ({code}). Change approach, or reply Stop to end; reply Continue to retry with a new strategy.',
  actionLoop:
    'Already ran {tool} {count} times on this page and stopped looping. Finish from the existing screenshot/page, or try another page.',
  transportAsk: 'Model request failed: {message}. Reply Continue to retry, or Stop to end.',
}

const zhCN: Copy = {
  acting: '正在执行…',
  actingSkill: '正在加载 skill：{id}',
  actingMcp: '正在调用 MCP：{tool}',
  actingAsk: '正在向你确认…',
  actingDone: '正在收尾…',
  actingSearch: '正在搜索：{query}',
  actingSearchEmpty: '正在搜索…',
  actingSub: '正在启动只读子任务…',
  actingTool: '正在执行工具：{tool}',
  timeout: 'Run 已超过墙钟上限 {minutes} 分钟，已停止以免空转。',
  tokenBudget: 'Run 已达到 token 预算 {budget}（当前累计 {used}），已停止。',
  privacy: {
    inject_denied: '控制台 → 隐私与数据 → 允许 DOM script 注入（保存后生效）',
    execute_js_denied: '控制台 → 隐私与数据 → 允许 DOM script 注入（保存后生效）',
    probe_denied: '控制台 → 隐私与数据 → 允许 MAIN world 只读探测（保存后生效）',
    intercept_denied: '控制台 → 隐私与数据 → 允许 Network 劫持（保存后生效）',
    no_body: '控制台 → 隐私与数据 → 捕获 Network 响应体预览（保存后生效）',
    attach_failed: '关闭目标页 DevTools / 其他调试扩展后重试',
    no_network: 'Side Panel 勾选 Enable Network plane',
    no_search_key: '设置 → 模型 → 网页搜索（Brave / Tavily）',
    shot_not_saved: '设置 → 工作区 → 启动本机助手（截图须写入 ~/NaviForge/shots）',
    page_not_saved: '设置 → 工作区 → 启动本机助手（导出须写入 ~/NaviForge/pages）',
    no_workspace: '设置 → 工作区 → 连接本机助手',
  },
  hardDeny:
    '工具 {tool} 被设置拒绝（{code}）。请到 {where} 开启对应开关后回复「继续」，或回复「停止」结束任务。不要反复调用同一被拒绝的工具。',
  hardDenySearch:
    '工具 {tool} 需要搜索密钥（{code}）。请到 {where} 后回复「继续」，或回复「停止」结束任务。禁止改去 Google 结果页硬爬。',
  sameFailureNav:
    'dom_navigate 连续失败 {count} 次：缺少 action/url。请改用 {"action":"url","url":"https://..."} 或 dom_click 点击列表项；禁止再传空 {}。回复「继续」换策略重试，或「停止」结束。',
  sameFailure:
    '工具 {tool} 连续失败 {count} 次（{code}）。请换一种做法，或回复「停止」结束；回复「继续」则换策略重试。',
  actionLoop:
    '同一页面已重复执行 {tool} {count} 次，已停止空转。请用已有截图/页面内容完成任务，或换页面后再试。',
  transportAsk: '模型请求失败：{message}。回复「继续」重试，或「停止」结束。',
}

const es: Copy = {
  acting: 'Trabajando…',
  actingSkill: 'Cargando skill: {id}',
  actingMcp: 'Llamando MCP: {tool}',
  actingAsk: 'Esperando tu respuesta…',
  actingDone: 'Cerrando…',
  actingSearch: 'Buscando: {query}',
  actingSearchEmpty: 'Buscando…',
  actingSub: 'Iniciando subtarea de solo lectura…',
  actingTool: 'Ejecutando {tool}',
  timeout: 'La ejecución alcanzó el límite de {minutes} minutos y se detuvo.',
  tokenBudget: 'La ejecución alcanzó el presupuesto de tokens {budget} (usados {used}) y se detuvo.',
  privacy: {
    inject_denied: 'Ajustes → Privacidad → Permitir inyección de script DOM (guardar para aplicar)',
    execute_js_denied: 'Ajustes → Privacidad → Permitir inyección de script DOM (guardar para aplicar)',
    probe_denied: 'Ajustes → Privacidad → Permitir sondeo de solo lectura MAIN (guardar para aplicar)',
    intercept_denied: 'Ajustes → Privacidad → Permitir interceptación de red (guardar para aplicar)',
    no_body: 'Ajustes → Privacidad → Capturar vistas previas del cuerpo de red (guardar para aplicar)',
    attach_failed: 'Cierra DevTools u otras extensiones de depuración en esta pestaña y reintenta',
    no_network: 'Panel lateral: activa el plano de red',
    no_search_key: 'Ajustes → Modelos → Búsqueda web (Brave / Tavily)',
    shot_not_saved: 'Ajustes → Espacio de trabajo → inicia el asistente local (capturas en ~/NaviForge/shots)',
    page_not_saved: 'Ajustes → Espacio de trabajo → inicia el asistente local (exporta a ~/NaviForge/pages)',
    no_workspace: 'Ajustes → Espacio de trabajo → conecta el asistente local',
  },
  hardDeny:
    'La herramienta {tool} está bloqueada por ajustes ({code}). Actívala en {where}, responde Continuar — o Detener para terminar. No reintentes la misma herramienta denegada.',
  hardDenySearch:
    'La herramienta {tool} necesita una clave de búsqueda ({code}). Añádela en {where}, responde Continuar — o Detener para terminar. No raspes resultados de Google.',
  sameFailureNav:
    'dom_navigate falló {count} veces: falta action/url. Usa {"action":"url","url":"https://..."} o haz clic en un elemento. {{}} vacío está prohibido. Responde Continuar para cambiar de estrategia, o Detener.',
  sameFailure:
    'La herramienta {tool} falló {count} veces ({code}). Cambia de enfoque, o responde Detener; Continuar reintenta con otra estrategia.',
  actionLoop:
    'Ya se ejecutó {tool} {count} veces en esta página y se detuvo el bucle. Termina con la captura/página existente, o prueba otra página.',
  transportAsk: 'Falló la petición al modelo: {message}. Responde Continuar para reintentar, o Detener.',
}

const COPY: Record<UiLocale, Copy> = { en, 'zh-CN': zhCN, es }

export function uiCopy(locale?: string): Copy {
  return COPY[resolveUiLocale(locale)]
}

export function fillCopy(template: string, vars: Record<string, string | number>): string {
  let text = template
  for (const [key, value] of Object.entries(vars)) {
    text = text.replaceAll(`{${key}}`, String(value))
  }
  return text
}
