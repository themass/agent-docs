/** Max parallel readonly leaves per spawn call (DeerFlow SubagentLimitMiddleware default). */
export const MAX_PARALLEL_SUBTASKS = 3

export type ReadonlySubtaskSpec = {
  /** Short label for trace/UI (DeerFlow `description`). */
  title: string
  /** Full isolated instructions (DeerFlow `prompt`). Child sees only this + user task line. */
  prompt: string
  /** Optional explicit URLs to open or fetch. */
  urls?: string[]
  /** `fetch` = static text via fetch_text; `tab` = JS/rendered page via tabs_open+dom_read. */
  mode?: 'fetch' | 'tab'
}

export function briefFromSubtask(spec: ReadonlySubtaskSpec): string {
  const title = spec.title.trim()
  const prompt = spec.prompt.trim()
  const urls = (spec.urls ?? []).map((u) => u.trim()).filter(Boolean)
  const mode = spec.mode ?? (urls.length ? 'tab' : undefined)

  const urlBlock =
    mode === 'fetch' && urls.length
      ? `Use fetch_text({ urls: ${JSON.stringify(urls)} }) for static content; if empty or not HTML, retry tabs_open on the primary URL.`
      : urls.length === 1
        ? `Start with tabs action=open ${urls[0]} then browser_observe / network as needed.`
        : urls.length > 1
          ? `Targets: ${urls.join(' | ')} — use fetch_text when static, else tabs open each tab target.`
          : ''

  return [
    title ? `[${title}]` : '',
    urlBlock,
    prompt,
    'Constraints: readonly only; no browser_act writes, browser_nav, js, spawn, or ask_user.',
    'Finish with system_done — return structured JSON or bullet list matching the requested fields.',
  ]
    .filter(Boolean)
    .join('\n')
}

function parseSubtask(raw: unknown): ReadonlySubtaskSpec | null {
  if (!raw || typeof raw !== 'object') return null
  const rec = raw as Record<string, unknown>
  const title = typeof rec.title === 'string' ? rec.title : typeof rec.description === 'string' ? rec.description : ''
  const prompt = typeof rec.prompt === 'string' ? rec.prompt : typeof rec.task === 'string' ? rec.task : ''
  if (!title.trim() || !prompt.trim()) return null
  const urls = Array.isArray(rec.urls)
    ? rec.urls.filter((u): u is string => typeof u === 'string' && u.trim().length > 0)
    : typeof rec.url === 'string' && rec.url.trim()
      ? [rec.url.trim()]
      : undefined
  const modeRaw = rec.mode
  const mode =
    modeRaw === 'fetch' || modeRaw === 'tab'
      ? modeRaw
      : modeRaw === 'fetch_text'
        ? 'fetch'
        : undefined
  return { title: title.trim(), prompt: prompt.trim(), urls, mode }
}

/** Accept legacy briefs[] or structured subtasks[] (DeerFlow-style title+prompt). */
export function normalizeSpawnBriefs(args: Record<string, unknown>): { briefs: string[] } | { error: string } {
  const rawSubtasks = args.subtasks ?? args.tasks
  if (Array.isArray(rawSubtasks) && rawSubtasks.length) {
    if (rawSubtasks.length > MAX_PARALLEL_SUBTASKS) {
      return { error: `subtasks must contain 1-${MAX_PARALLEL_SUBTASKS} items` }
    }
    const briefs: string[] = []
    for (const item of rawSubtasks) {
      const spec = parseSubtask(item)
      if (!spec) return { error: 'each subtask needs title (or description) and prompt (or task)' }
      briefs.push(briefFromSubtask(spec))
    }
    return { briefs }
  }

  const rawBriefs = args.briefs
  if (!Array.isArray(rawBriefs) || !rawBriefs.length) {
    return { error: 'provide briefs[] or subtasks[{title,prompt,urls?,mode?}]' }
  }
  if (rawBriefs.length > MAX_PARALLEL_SUBTASKS) {
    return { error: `briefs must contain 1-${MAX_PARALLEL_SUBTASKS} non-empty strings` }
  }
  const briefs = rawBriefs.filter((b): b is string => typeof b === 'string' && b.trim().length > 0)
  if (briefs.length !== rawBriefs.length) {
    return { error: `briefs must contain 1-${MAX_PARALLEL_SUBTASKS} non-empty strings` }
  }
  return { briefs }
}

/** Leaf readonly sub-agent system append. */
export const READONLY_CHILD_KERNEL_SECTION = `## 只读子 Agent
你由 Lead 通过 system_spawn_readonly_tasks 派出；消息里只有本子任务 brief。

≤16 步内完成并 system_done。静态 URL → fetch_text；需 JS/播放器 → tabs open → browser_observe / network / PAGE SIGNALS。
禁止：DOM 写、browser_nav、js、嵌套 spawn、system_ask_user。返回结构化 JSON 或 bullet；缺字段说明 shortfall，勿编造。`

export const SUBTASK_KERNEL_SECTION = `## 委派：只读子任务（system_spawn_readonly_tasks）

你是 **Lead**：规划、委派、汇总。子 Agent 只做独立只读片；最终 system_done 由你写用户可见结论（合并 children[]，禁止裸贴日志）。

**何时委派** — 2+ 互不依赖 URL；或 navigation:forbidden 但详情在别的页；或批量只读可并行。
**自己完成** — 单页一次 fetch_text 或 browser_observe 够；有顺序依赖则分批 spawn；写 DOM/登录/HITL 由父 Agent 做。

**并行**：一次 spawn 最多 **${MAX_PARALLEL_SUBTASKS}** 条 subtasks[]。更多则多轮 spawn，每轮汇总再继续。
**禁止**：navigation:forbidden 时父 tab 串行打开列表项；用 spawn 代替。

**subtasks[]**：每项 title + prompt + 可选 urls、mode（fetch=静态 fetch_text，tab=tabs+observe/network）。
子 Agent 只读：禁止写 DOM、嵌套 spawn、system_ask_user。`

export const PARALLEL_SUBTASK_GUIDANCE: readonly string[] = [
  'GUIDANCE: traverse — spawn 并行补全列表/详情；子 prompt 写清要返回的字段。',
  'GUIDANCE: subtasks[] 每项含 title + prompt + urls? + mode(fetch|tab)。静态 → fetch_text；渲染页 → tabs+browser_observe。',
  `GUIDANCE: 待处理 >${MAX_PARALLEL_SUBTASKS}：多轮 spawn，每轮汇总 children[] 再派下一批。你写最终 system_done（合并结果），禁止裸贴 child 日志。`,
  'GUIDANCE: spawn 子任务返回 children 后，若证据已够对比/总结，直接 system_done；勿 tabs list 空转。',
  'GUIDANCE: 媒体任务 — 直链写 mediaUrl+format；仅内嵌播放器写 playPageUrl+shortfall。',
]

export const PARALLEL_SUBTASK_STATIC_URL_HINT =
  'GUIDANCE: 已知静态 document/API URL 设 mode:fetch；仅 JS 渲染页用 mode:tab。'
