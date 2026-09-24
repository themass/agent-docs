import { chatCompletion, type LlmConfig, type LlmUsage } from './llm.js'
import type { OpenAiFunctionTool } from '@naviforge/shared'

const SYSTEM_DONE_TOOL: OpenAiFunctionTool = {
  type: 'function',
  function: {
    name: 'system_done',
    description: 'Return the final answer.',
    parameters: {
      type: 'object',
      properties: { result: { type: 'string' } },
      required: ['result'],
      additionalProperties: false,
    },
  },
}

function systemDoneResult(completion: Awaited<ReturnType<typeof chatCompletion>>): string {
  const calls = completion.toolCalls
  if (calls?.length === 1 && calls[0]?.name === 'system_done') {
    const result = calls[0].arguments.result
    if (typeof result === 'string' && result.trim()) return result.trim()
  }
  // ponytail: some vision/OCR gateways return plain text instead of tool_calls
  const plain = completion.content.trim()
  if (plain) return plain
  throw new Error('模型未返回识别结果，请换 OCR 模型或检查 API 配置')
}

export const PAGE_ASK_SYSTEM = `你是看图助手。用户提供了一张图片（页面截图、工作区截图或本地上传），以及可选的页面文本摘录。
根据这些证据回答用户问题。
- 不要编造图上看不到的内容；看不清或摘录不足时如实说明。
- 优先依据图片中的可见信息；文本摘录仅作补充。
- 回答简洁、可用条目或短段落，不要展开成操作计划。
- 必须恰好调用一次 system_done，并将答案放在 result。`

export const PAGE_TEXT_SYSTEM = `你是页面理解助手。用户提供了当前浏览器页面的正文摘录，没有截图。
根据正文回答用户问题。
- 不要编造正文里没有的内容；摘录不足时如实说明。
- 回答简洁、可用条目或短段落，不要展开成操作计划。
- 必须恰好调用一次 system_done，并将答案放在 result。`

export const PAGE_SUMMARIZE_QUESTION =
  '总结本页：这是什么、适合谁、关键要点。正文不足时如实说明，不要编造。'

export function explainPickedQuestion(label: string): string {
  return `解释选中的元素「${label}」：它是什么、做什么、点了会发生什么。看不到的不要编造。`
}

export function resolveOneShotQuestion(
  kind: 'page' | 'summarize' | 'explain',
  typed: string,
  pickedLabel?: string
): string {
  const question = typed.trim()
  if (question) return question
  if (kind === 'summarize') return PAGE_SUMMARIZE_QUESTION
  if (kind === 'explain') return explainPickedQuestion(pickedLabel?.trim() || '选中元素')
  return ''
}

export function pickedElementExcerpt(element: {
  tag?: string
  title?: string
  text?: string
  selector?: string
}): string {
  return [
    element.tag ? `标签: ${element.tag}` : '',
    element.title ? `标题: ${element.title}` : '',
    element.selector ? `选择器: ${element.selector}` : '',
    element.text ? `文本: ${element.text}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}

export type AskAboutPageInput = {
  llm: LlmConfig
  question: string
  /** Viewport screenshot. Omit for text-only one-shots (summarize). */
  imageDataUrl?: string
  url?: string
  title?: string
  /** Compact DOM / text excerpt — required when `imageDataUrl` is omitted. */
  textExcerpt?: string
  signal?: AbortSignal
}

export type AskAboutPageResult = {
  answer: string
  usage?: LlmUsage
}

/** One-shot page Q&A — not an agent tool loop. Screenshot optional when excerpt is present. */
export async function askAboutPage(input: AskAboutPageInput): Promise<AskAboutPageResult> {
  const question = input.question.trim()
  if (!question) throw new Error('问题不能为空')
  const image = input.imageDataUrl
  if (image && !image.startsWith('data:image/')) {
    throw new Error('需要有效的图片')
  }
  const excerptCap = image ? 6_000 : 12_000
  const excerpt = input.textExcerpt?.trim().slice(0, excerptCap)
  if (!image && !excerpt) {
    throw new Error('需要页面截图或正文摘录')
  }
  const user = [
    `页面 URL：${input.url ?? '(unknown)'}`,
    `页面标题：${input.title ?? '(unknown)'}`,
    excerpt ? `页面文本摘录：\n${excerpt}` : '',
    `用户问题：\n${question}`,
  ]
    .filter(Boolean)
    .join('\n\n')
  const completion = await chatCompletion(input.llm, image ? PAGE_ASK_SYSTEM : PAGE_TEXT_SYSTEM, user, {
    signal: input.signal,
    imageDataUrl: image,
    tools: [SYSTEM_DONE_TOOL],
  })
  return { answer: systemDoneResult(completion), usage: completion.usage }
}

export const OCR_SYSTEM = `你是文字识别助手。用户提供了一张网页选区截图。
只转录图中可见文字，保持原有换行。
看不清的字写 [看不清]。
不要总结、翻译、解释，也不要补全图上没有的字。
必须恰好调用一次 system_done，并将转录放在 result。`

export type OcrImageInput = {
  llm: LlmConfig
  imageDataUrl: string
  signal?: AbortSignal
}

export type OcrImageResult = {
  text: string
  usage?: LlmUsage
}

/** One-shot screenshot transcription — not an agent tool loop. */
export async function ocrImage(input: OcrImageInput): Promise<OcrImageResult> {
  if (!input.imageDataUrl.startsWith('data:image/')) {
    throw new Error('需要有效的选区截图')
  }
  const completion = await chatCompletion(input.llm, OCR_SYSTEM, '请原样转录图中全部可见文字。', {
    signal: input.signal,
    imageDataUrl: input.imageDataUrl,
    tools: [SYSTEM_DONE_TOOL],
  })
  return { text: systemDoneResult(completion), usage: completion.usage }
}
