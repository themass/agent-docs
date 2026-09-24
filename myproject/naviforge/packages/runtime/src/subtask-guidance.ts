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
        ? `Start with tabs_open ${urls[0]} then dom_read / network_read as needed.`
        : urls.length > 1
          ? `Targets: ${urls.join(' | ')} — use fetch_text when static, else tabs_open each tab target.`
          : ''

  return [
    title ? `[${title}]` : '',
    urlBlock,
    prompt,
    'Constraints: readonly only; no dom_click/dom_navigate/execute_js/spawn/ask_user.',
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

/** Leaf readonly sub-agent system append (DeerFlow general-purpose readonly slice). */
export const READONLY_CHILD_KERNEL_SECTION = `## 只读子 Agent 角色
你是父 Lead Agent 派出的**只读 Worker**。用户消息里只有本条子任务 brief；看不到父对话、其它子任务、列表页 snapshot。

职责：在 ≤16 步内完成指派只读工作并 system_done。
- 静态 URL / JSON / raw 文档 → fetch_text（可 urls 数组）
- 需 JS / cookie / 播放器 inline 配置 → tabs_open（后台 tab）→ dom_read body / network_read / PAGE SIGNALS
禁止：DOM 写、dom_navigate、execute_js、嵌套 spawn、system_ask_user。
结果：system_done 返回结构化 JSON 或 bullet；缺字段时说明原因，不要编造。`

/** Lead Agent delegation block (DeerFlow task + OpenHarness delegation). */
export const SUBTASK_KERNEL_SECTION = `## 委派：并行只读子任务（system_spawn_readonly_tasks）

### 你的角色（Lead / Orchestrator）
你负责规划、委派、**汇总**。子 Agent 只做独立只读片；最终 system_done 必须由你写用户可见结论（合并 children[]，禁止裸贴原始日志）。

### 何时委派（OpenHarness：仅当 materially helps）
**委派** — 满足任一：
- **2+ 互不依赖**的 URL/页面要读或抽取字段
- 父任务 navigation:forbidden，但数据在多个详情/播放/商品页
- 批量只读，可拆成并行片（长周期任务）

**自己做完** — 满足任一：
- 单 URL / 单页 / 单次 fetch_text 或 dom_read 够
- 子任务有顺序依赖（B 依赖 A 的输出）→ 先一批 spawn，汇总后再下一批
- 需要 DOM 写、登录、HITL、表单提交

### 并行 vs 串行（DeerFlow）
- **并行**：同一轮 spawn 打包最多 **${MAX_PARALLEL_SUBTASKS}** 条独立 subtask（一次 tool call，内部 Promise.all）
- **串行批次**：待处理 >${MAX_PARALLEL_SUBTASKS} 条 → 多轮 spawn；每轮等 children[] 返回再派下一批
- 禁止父 tab 串行 dom_navigate 逐个打开列表项（尤其 navigation:forbidden 时）

### 如何写 subtask（DeerFlow description + prompt）
优先 structured **subtasks[]**（比裸 briefs 更不易丢字段）：
\`\`\`json
{
  "subtasks": [
    {
      "title": "Item 101 price",
      "prompt": "Extract product name, price, currency, SKU. Return JSON {name,price,currency,sku}.",
      "urls": ["https://shop.example/p/101"],
      "mode": "tab"
    }
  ]
}
\`\`\`

**好 prompt ✅**（具体、可验证、含输出格式）  
\`Extract name, price, SKU from the product page; return JSON {name,price,sku}.\`

**差 prompt ❌**  
\`Research this page\` / \`Get video info\`

legacy **briefs[]** 仍可用：每条必须是**自包含**完整 brief（含 URL、字段、system_done 格式）。

### 模式选择
| 场景 | 子 Agent 路径 |
|------|----------------|
| 静态 HTML / API / raw | mode: fetch → fetch_text |
| JS 渲染 / 播放器 / 需 cookie | mode: tab → tabs_open → dom_read / network_read |

### 汇总与失败（Lead 责任）
- spawn 返回 children[{status, result}]：**合并**成功项；对 failed/缺字段项可新一批 retry
- partial OK → system_done 说明已覆盖范围与缺口
- 禁止在列表页 execute_js / network_read 空转代替 spawn

### 示例：三页并行一批（媒体）
\`\`\`json
{
  "subtasks": [
    {
      "title": "vod-1",
      "prompt": "Read PAGE SIGNALS. Return JSON: {title, listUrl, mediaUrl?, playPageUrl?, format?, confidence?, shortfall?}. Direct stream (m3u8/mp4/webm/mpd) → mediaUrl; embed-only → playPageUrl.",
      "urls": ["https://example/v/1"],
      "mode": "tab"
    }
  ]
}
\`\`\`
详细 playbook：**catalog-crawl-sop**（Phase 0–5）。媒体输出 schema 见 GUIDANCE MEDIA_ENTRY。
`

export const PARALLEL_SUBTASK_GUIDANCE: readonly string[] = [
  'GUIDANCE: catalog-crawl-sop Phase 3 — spawn 并行补全列表/媒体；子 prompt 含 MEDIA_ENTRY JSON schema。',
  'GUIDANCE: subtasks[] 每项含 title + prompt + urls? + mode(fetch|tab)。静态 → fetch_text；渲染页 → tabs_open+dom_read+PAGE SIGNALS。',
  `GUIDANCE: 待处理 >${MAX_PARALLEL_SUBTASKS}：多轮 spawn，每轮汇总 children[] 再派下一批。你写最终 system_done（合并结果），禁止裸贴 child 日志。`,
  'GUIDANCE: spawn 子任务返回 children 后，若证据已够对比/总结，直接 system_done；勿 tabs_list 空转。',
  'GUIDANCE: 媒体任务 — 直链写 mediaUrl+format；仅内嵌播放器写 playPageUrl+shortfall；多候选由你结合 PAGE SIGNALS 判断。',
]

export const PARALLEL_SUBTASK_STATIC_URL_HINT =
  'GUIDANCE: 已知静态 document/API URL 设 mode:fetch；仅 JS 渲染页用 mode:tab。'
