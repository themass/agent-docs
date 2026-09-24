import type { ToolResult } from '@naviforge/shared'
import type { PageSignalCollectPayload } from './page-signals.js'

export type SnapshotMode = 'compact' | 'viewport' | 'full'

export type DomSnapshot = {
  revision: number
  url: string
  title: string
  header: string
  content: string
  footer: string
  /** Same-origin iframe / open-shadow supplement (optional). */
  frames?: string
  /** How this snapshot was requested; omitted = default prompt budget. */
  mode?: SnapshotMode
}

export type DomExtractItem = {
  index?: number
  kind: 'link' | 'button' | 'input' | 'feed' | 'heading' | 'other'
  title: string
  href?: string
  tag: string
}

export type DomExtractResult = {
  url: string
  title: string
  items: DomExtractItem[]
  links: DomExtractItem[]
  buttons: DomExtractItem[]
  feeds: DomExtractItem[]
}

export type DomContentItem = {
  label: string
  index: number
  title: string
  url?: string
  author?: string
  views?: string
  duration?: string
  /** Every field the extractor read out of the record (price, rating, episode…). */
  fields?: Record<string, string>
  confidence?: number
}

export type DomMarkTopnResult = {
  marked: number
  candidates: number
  items: DomContentItem[]
  /** How the records were found: a site profile, structural induction, or a fallback scan. */
  strategy?: string
  profileId?: string
  /** Set when fewer records were found than requested — report it, never pad. */
  shortfall?: string
}

export type DomHighlightTarget = {
  /** Snapshot interactive index (preferred when revision is fresh). */
  index?: number
  /** Stable CSS selector fallback. */
  selector?: string
  /** Badge text shown on the mark (e.g. "TOP1"). */
  label: string
  color?: string
}

export type DomInjectKind = 'css' | 'html' | 'script'

/**
 * Browser DOM plane. Implementations must run actions in an isolated world
 * (content script), not page MAIN JS — except explicit `inject` of kind script
 * which still runs in the content-script world, never page MAIN.
 */
export type DomReadPageResult = {
  text: string
  source: string
  truncated: boolean
  title: string
  url: string
}

export type DomPageMarkdownResult = {
  markdown: string
  title: string
  url: string
  source: string
}

export type DomPagePdfResult = {
  dataUrl: string
  title: string
  url: string
}

export interface DomPlane {
  snapshot(opts?: { mode?: SnapshotMode }): Promise<ToolResult<DomSnapshot>>
  /** Readable article/main/body text — use for summarize / Q&A, not list extraction. */
  readPage?(opts?: { timeoutMs?: number }): Promise<ToolResult<DomReadPageResult>>
  /** Current page → Markdown (Readability + Turndown). Caller writes the file. */
  toMarkdown?(): Promise<ToolResult<DomPageMarkdownResult>>
  /** Current page → PDF via Chrome printToPDF. Caller writes the file. */
  toPdf?(): Promise<ToolResult<DomPagePdfResult>>
  click(index: number, revision: number, framePath?: string): Promise<ToolResult<{ message: string }>>
  type(index: number, text: string, revision: number): Promise<ToolResult<{ message: string }>>
  /** Returns a stable CSS selector candidate for a current snapshot index. */
  selector(index: number, revision: number): Promise<ToolResult<{ selector?: string }>>
  /** Optional stable Playbook fallback; selectors are executed in isolated content scripts. */
  clickSelector?(selector: string): Promise<ToolResult<{ message: string }>>
  typeSelector?(selector: string, text: string): Promise<ToolResult<{ message: string }>>
  /** Paint scroll-following marks on elements (outline + floating badge). */
  highlight?(
    targets: DomHighlightTarget[],
    revision?: number
  ): Promise<ToolResult<{ marked: number }>>
  /** Mark the page's top records in reading order (TOP1..TOPn). */
  markTopn?(n: number, opts?: { showHints?: boolean }): Promise<ToolResult<DomMarkTopnResult>>
  /** Read records without touching the page — titles, links and fields only. */
  extractContent?(n: number): Promise<ToolResult<DomMarkTopnResult>>
  /** Paint marks on records already returned by `extractContent`. */
  markItems?(
    items: Array<{ index: number; label?: string; detail?: string }>
  ): Promise<ToolResult<{ marked: number; missed?: number[] }>>
  clearHighlights?(): Promise<ToolResult<{ cleared: true }>>
  /**
   * Controlled injection in the content-script isolated world.
   * `script` must be explicitly allowed by the caller/settings gate.
   */
  inject?(opts: {
    kind: DomInjectKind
    code: string
    allowScript?: boolean
  }): Promise<ToolResult<{ message: string }>>
  /**
   * Run async JS in the page MAIN world and return JSON-safe data.
   * Read-only by convention (fetch / querySelectorAll). DOM writes use `inject`.
   */
  executeJs?(opts: {
    code: string
    timeoutMs?: number
    allowScript?: boolean
  }): Promise<ToolResult<{ result: unknown }>>
  /** Structured DOM extraction: links, buttons, feed cards with titles/hrefs. */
  extractDom?(opts?: {
    kind?: 'all' | 'links' | 'buttons' | 'feeds'
    limit?: number
  }): Promise<ToolResult<DomExtractResult>>
  navigate?(
    action: 'back' | 'forward' | 'reload' | 'url',
    url?: string
  ): Promise<ToolResult<{ message: string }>>
  scroll?(opts: {
    to?: 'top' | 'bottom' | 'y'
    y?: number
    direction?: 'up' | 'down'
    amount?: number
  }): Promise<ToolResult<{ message: string }>>
  wait?(opts: {
    kind: 'stable' | 'text' | 'network_idle' | 'download'
    text?: string
    timeoutMs?: number
  }): Promise<ToolResult<{ message: string }>>
  press?(key: string, modifiers?: string[]): Promise<ToolResult<{ message: string }>>
  select?(index: number, value: string, revision: number): Promise<ToolResult<{ message: string }>>
  check?(index: number, checked: boolean, revision: number): Promise<ToolResult<{ message: string }>>
  upload?(
    index: number,
    filename: string,
    contentBase64: string,
    revision: number
  ): Promise<ToolResult<{ message: string }>>
  hover?(index: number, revision: number): Promise<ToolResult<{ message: string }>>
  drag?(
    fromIndex: number,
    toIndex: number,
    revision: number
  ): Promise<ToolResult<{ message: string }>>
  screenshot?(): Promise<ToolResult<{ dataUrl: string }>>
  /** Scroll the page and stitch viewport captures into one image. */
  screenshotFullPage?(): Promise<ToolResult<{ dataUrl: string; width: number; height: number; slices: number }>>
  /** Raw inline scripts, meta, resources for Page Signal mining. */
  collectPageSignalRaw?(): Promise<ToolResult<PageSignalCollectPayload>>
}
