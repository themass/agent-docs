import type { OpenAiFunctionTool } from '@naviforge/shared'

/** OpenAI-compatible `reasoning_effort`. Omit on the wire when thinking is off. */
export type ReasoningEffort = 'low' | 'medium' | 'high' | 'xhigh'

export type LlmConfig = {
  baseURL: string
  apiKey: string
  model: string
  reasoningEffort?: ReasoningEffort
}

/** OpenAI-compatible usage; absent when the gateway omits it. */
export type LlmUsage = {
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export type LlmToolCall = {
  name: string
  arguments: Record<string, unknown>
}

export type ChatCompletionResult = {
  /** `message.content` — empty when the model only emitted tool_calls or reasoning. */
  content: string
  /** `message.reasoning_content` when the gateway sends it (kept separate from content). */
  reasoning?: string
  usage?: LlmUsage
  toolCalls?: LlmToolCall[]
}

export type ChatCompletionOptions = {
  signal?: AbortSignal
  imageDataUrl?: string
  tools?: OpenAiFunctionTool[]
}

type ChatMessage =
  | { role: 'system' | 'user'; content: string }
  | {
      role: 'user'
      content: Array<{ type: 'text'; text: string } | { type: 'image_url'; image_url: { url: string } }>
    }

function parseUsage(raw: unknown): LlmUsage | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const u = raw as Record<string, unknown>
  const prompt = Number(u.prompt_tokens ?? u.input_tokens ?? 0)
  const completion = Number(u.completion_tokens ?? u.output_tokens ?? 0)
  const total = Number(u.total_tokens ?? prompt + completion)
  if (![prompt, completion, total].every((n) => Number.isFinite(n))) return undefined
  if (prompt === 0 && completion === 0 && total === 0) return undefined
  return { promptTokens: prompt, completionTokens: completion, totalTokens: total || prompt + completion }
}

function parseToolCalls(message: {
  tool_calls?: Array<{ function?: { name?: string; arguments?: string } }>
}): LlmToolCall[] | undefined {
  const calls = message.tool_calls
  if (!Array.isArray(calls) || !calls.length) return undefined
  const out: LlmToolCall[] = []
  for (const call of calls) {
    const name = call.function?.name?.trim() ?? ''
    let args: Record<string, unknown> = {}
    const raw = call.function?.arguments
    if (typeof raw === 'string' && raw.trim()) {
      try {
        const parsed = JSON.parse(raw) as unknown
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          args = parsed as Record<string, unknown>
        }
      } catch {
        args = { _raw: raw }
      }
    }
    out.push({ name, arguments: args })
  }
  return out
}

function toolChoiceForRequest(config: LlmConfig): 'required' | 'auto' {
  if (config.reasoningEffort) return 'auto'
  const model = config.model.toLowerCase()
  // DeepSeek reasoner / V4: thinking on by default; rejects tool_choice=required (vendor quirk).
  if (/deepseek[-_]?(reasoner|v4|r1)/.test(model) || model.startsWith('deepseek-v4')) return 'auto'
  return 'required'
}

/** Some gateways (e.g. Kimi/Moonshot) reject temperature≠1. */
function temperatureForRequest(config: LlmConfig): number {
  const model = config.model.toLowerCase()
  if (/kimi|moonshot/.test(model)) return 1
  return 0
}

function temperatureRetryAllowed(errBody: string): boolean {
  return /invalid temperature/i.test(errBody) && /only\s*1/i.test(errBody)
}

function buildChatBody(
  config: LlmConfig,
  system: string,
  userMessage: ChatMessage,
  opts: ChatCompletionOptions | undefined,
  temperature: number
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    model: config.model,
    temperature,
    messages: [{ role: 'system', content: system }, userMessage],
  }
  if (opts?.tools?.length) {
    body.tools = opts.tools
    body.tool_choice = toolChoiceForRequest(config)
  }
  if (config.reasoningEffort) body.reasoning_effort = config.reasoningEffort
  return body
}

/** OpenAI-compatible chat.completions — prefers native tools[] / tool_calls when provided. */
export async function chatCompletion(
  config: LlmConfig,
  system: string,
  user: string,
  opts?: ChatCompletionOptions
): Promise<ChatCompletionResult> {
  const base = config.baseURL.replace(/\/$/, '')
  const userMessage: ChatMessage = opts?.imageDataUrl
    ? {
        role: 'user',
        content: [
          { type: 'text', text: user },
          { type: 'image_url', image_url: { url: opts.imageDataUrl } },
        ],
      }
    : { role: 'user', content: user }
  const timeoutMs = 120_000 // ponytail: single ceiling; raise if your gateway is slower
  const timeoutSignal = AbortSignal.timeout(timeoutMs)
  const signal = opts?.signal
  const requestSignal =
    signal != null && typeof AbortSignal.any === 'function'
      ? AbortSignal.any([signal, timeoutSignal])
      : signal ?? timeoutSignal
  const url = `${base}/chat/completions`
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${config.apiKey}`,
  }
  let temperature = temperatureForRequest(config)
  let body = buildChatBody(config, system, userMessage, opts, temperature)
  let res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: requestSignal,
  })
  if (!res.ok) {
    const errBody = await res.text().catch(() => '')
    if (temperature !== 1 && res.status === 400 && temperatureRetryAllowed(errBody)) {
      temperature = 1
      body = buildChatBody(config, system, userMessage, opts, temperature)
      res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: requestSignal,
      })
      if (!res.ok) {
        const retryErr = await res.text().catch(() => '')
        throw new Error(`LLM HTTP ${res.status}: ${retryErr.slice(0, 400)}`)
      }
    } else {
      throw new Error(`LLM HTTP ${res.status}: ${errBody.slice(0, 400)}`)
    }
  }
  const json = (await res.json()) as {
    choices?: Array<{
      message?: {
        content?: string | null
        reasoning_content?: string | null
        tool_calls?: Array<{ function?: { name?: string; arguments?: string } }>
      }
    }>
    usage?: unknown
  }
  const message = json.choices?.[0]?.message
  const toolCalls = message ? parseToolCalls(message) : undefined
  const content = (message?.content ?? '').trim()
  const reasoning = (message?.reasoning_content ?? '').trim() || undefined
  return {
    content,
    reasoning,
    usage: parseUsage(json.usage),
    toolCalls,
  }
}
