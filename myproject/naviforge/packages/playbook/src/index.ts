import type { DomPlane } from '@naviforge/dom-plane'
import type { NetworkEvent, NetworkPlane, NetworkWaitOpts } from '@naviforge/network-plane'
import type { ToolResult } from '@naviforge/shared'

export type PlaybookStep =
  | { id: string; use: 'dom_type'; index: number; text: string; selector?: string }
  | { id: string; use: 'dom_click'; index: number; selector?: string }
  | { id: string; use: 'network_wait'; with: NetworkWaitOpts }
  | { id: string; use: 'dom_snapshot' }
  | { id: string; use: 'assert.text'; includes: string }

/** Successful DOM actions recorded during an Agent run (Teach input). */
export type RecordedDomAction =
  | { tool: 'dom_click'; index: number; selector?: string; network?: NetworkEvent }
  | { tool: 'dom_type'; index: number; text: string; selector?: string }

export type Playbook = {
  schemaVersion: 1
  playbookVersion: number
  id: string
  title: string
  task?: string
  host?: string
  createdAt: number
  inputs?: Record<string, { label: string; default?: string }>
  steps: PlaybookStep[]
  /** Optional post-run checks against the latest DOM snapshot text. */
  assertions?: Array<{ includes: string }>
}

export type PlaybookRunResult = {
  ok: boolean
  traces: string[]
  error?: string
}

/** Replace the deliberately small Phase 3 input syntax: `${inputs.name}`. */
export function resolvePlaybookText(text: string, inputs: Record<string, string>): string {
  return text.replace(/\$\{inputs\.([A-Za-z_][\w-]*)\}/g, (match, name: string) => {
    return Object.hasOwn(inputs, name) ? inputs[name] : match
  })
}

/**
 * Turn recorded literal text into editable inputs. Names are intentionally
 * generic (`value1`, `value2`) because the DOM index does not expose a stable
 * field label yet; the user can rename them in the JSON editor.
 */
export function parameterizePlaybook(playbook: Playbook): Playbook {
  let inputNumber = 0
  const inputs: NonNullable<Playbook['inputs']> = { ...(playbook.inputs ?? {}) }
  const steps = playbook.steps.map((step) => {
    if (step.use !== 'dom_type' || step.text.includes('${inputs.')) return step
    inputNumber += 1
    const name = `value${inputNumber}`
    inputs[name] = { label: `Input ${inputNumber}`, default: step.text }
    return { ...step, text: `\${inputs.${name}}` }
  })
  return { ...playbook, inputs: Object.keys(inputs).length ? inputs : undefined, steps }
}

/** Prefer an explicit stable selector; index remains the backwards-compatible fallback. */
export function resolveStepTarget(step: Extract<PlaybookStep, { index: number }>): {
  index: number
  selector?: string
} {
  return { index: step.index, selector: step.selector?.trim() || undefined }
}

/** Keep requests portable by matching only the pathname, method and status. */
export function networkExpectationFor(event: NetworkEvent): NetworkWaitOpts {
  let urlIncludes = event.url
  try {
    urlIncludes = new URL(event.url).pathname
  } catch {
    // use the raw URL when it is not parseable
  }
  return {
    urlIncludes,
    method: event.method,
    status: event.status,
    timeoutMs: 10000,
  }
}

/** Forge a playbook from successful DOM actions only (drops failed / network / done). */
export function forgePlaybook(opts: {
  id?: string
  title: string
  task?: string
  host?: string
  actions: RecordedDomAction[]
  playbookVersion?: number
}): Playbook | null {
  const steps: PlaybookStep[] = []
  let i = 0
  for (const a of opts.actions) {
    i += 1
    if (a.tool === 'dom_click') {
      steps.push({ id: `s${i}`, use: 'dom_click', index: a.index, selector: a.selector })
      if (a.network) {
        i += 1
        steps.push({ id: `s${i}`, use: 'network_wait', with: networkExpectationFor(a.network) })
      }
    } else if (a.tool === 'dom_type') {
      steps.push({ id: `s${i}`, use: 'dom_type', index: a.index, text: a.text, selector: a.selector })
    }
  }
  if (!steps.length) return null
  return {
    schemaVersion: 1,
    playbookVersion: opts.playbookVersion ?? 1,
    id: opts.id ?? `pb-${Date.now().toString(36)}`,
    title: opts.title,
    task: opts.task,
    host: opts.host,
    createdAt: Date.now(),
    steps,
  }
}

/** Deterministic runner — no LLM. */
export async function runPlaybook(
  dom: DomPlane,
  pb: Playbook,
  inputs: Record<string, string> = {},
  network?: NetworkPlane
): Promise<PlaybookRunResult> {
  const traces: string[] = []
  for (const step of pb.steps) {
    if (step.use === 'dom_snapshot') {
      const r = await dom.snapshot()
      traces.push(trace(step.id, r))
      if (!r.ok) return { ok: false, traces, error: r.error.message }
      continue
    }
    if (step.use === 'network_wait') {
      if (!network) {
        return { ok: false, traces, error: `${step.id}: Network Plane is required` }
      }
      const r = await network.wait(step.with)
      traces.push(trace(step.id, r))
      if (!r.ok) return { ok: false, traces, error: r.error.message }
      continue
    }
    if (step.use === 'assert.text') {
      const snap = await dom.snapshot()
      if (!snap.ok) return { ok: false, traces, error: snap.error.message }
      const haystack = `${snap.data.title}\n${snap.data.header}\n${snap.data.content}\n${snap.data.footer}`
      if (!haystack.includes(step.includes)) {
        return {
          ok: false,
          traces: [...traces, `${step.id}: assert fail missing "${step.includes}"`],
          error: `assert.text: "${step.includes}" not found in snapshot`,
        }
      }
      traces.push(`${step.id}: assert ok "${step.includes}"`)
      continue
    }
    const snap = await dom.snapshot()
    if (!snap.ok) return { ok: false, traces, error: snap.error.message }
    const rev = snap.data.revision
    if (step.use === 'dom_click') {
      const target = resolveStepTarget(step)
      const r = target.selector && dom.clickSelector
        ? await dom.clickSelector(target.selector)
        : await dom.click(target.index, rev)
      traces.push(trace(step.id, r))
      if (!r.ok) return { ok: false, traces, error: r.error.message }
    } else if (step.use === 'dom_type') {
      const target = resolveStepTarget(step)
      const text = resolvePlaybookText(step.text, inputs)
      const r = target.selector && dom.typeSelector
        ? await dom.typeSelector(target.selector, text)
        : await dom.type(target.index, text, rev)
      traces.push(trace(step.id, r))
      if (!r.ok) return { ok: false, traces, error: r.error.message }
    }
  }
  if (pb.assertions?.length) {
    const snap = await dom.snapshot()
    if (!snap.ok) return { ok: false, traces, error: snap.error.message }
    const haystack = `${snap.data.title}\n${snap.data.header}\n${snap.data.content}\n${snap.data.footer}`
    for (const [index, assertion] of pb.assertions.entries()) {
      const id = `assert-${index + 1}`
      if (!haystack.includes(assertion.includes)) {
        return {
          ok: false,
          traces: [...traces, `${id}: fail missing "${assertion.includes}"`],
          error: `assertion: "${assertion.includes}" not found`,
        }
      }
      traces.push(`${id}: ok "${assertion.includes}"`)
    }
  }
  return { ok: true, traces }
}

function trace(id: string, r: ToolResult): string {
  return r.ok ? `${id}: ok` : `${id}: fail ${r.error.message}`
}

