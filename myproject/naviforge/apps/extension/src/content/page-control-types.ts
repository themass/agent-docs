import type { PageController } from '@page-agent/page-controller'

import type { ExtractReport } from '../lib/content-extract'

export type PageControlSendResponse = (response: unknown) => void

export interface PageControlPayload extends Record<string, unknown> {
  phase?: string
  text?: string
  path?: string
  mode?: string
  kind?: 'all' | 'links' | 'buttons' | 'feeds' | 'css' | 'html' | 'script' | string
  limit?: number
  framePath?: string
  index?: number
  injectKind?: string
  code?: string
  allowScript?: boolean
  timeout_ms?: number
  action?: string
  url?: string
  y?: number
  behavior?: ScrollBehavior
  waitKind?: string
  key?: string
  modifiers?: string[]
  value?: string
  checked?: boolean
  contentBase64?: string
  filename?: string
  fromIndex?: number
  toIndex?: number
  n?: number
  showHints?: boolean
  selector?: string
  label?: string
  targets?: Array<{ label?: string; index?: number; selector?: string; color?: string }>
  items?: Array<{ index: number; label?: string; detail?: string }>
  op?: string
  cues?: Array<{ start: number; end: number; text: string; translated: string }>
}

export type PageControlMark = {
  element: Element
  anchor: HTMLElement
  overlay: HTMLElement
  badge: HTMLElement
  tooltip?: HTMLElement
  color: string
  label: string
}

export interface PageControlContext {
  revision: { current: number }
  TOP_COLORS: readonly string[]
  marks: Map<string, PageControlMark>
  pageSelectionText: (liveOnly?: boolean) => string
  startElementPick: () => void
  startRegionCrop: (options?: { hint?: string }) => Promise<{
    success: boolean
    cancelled?: boolean
    rect?: { x: number; y: number; width: number; height: number }
    devicePixelRatio?: number
    error?: string
  }>
  showOcrHud: (payload: { phase?: string; text?: string; path?: string }) => void
  getPc: () => PageController
  entriesFromSelectorMapLocal: () => Array<{ index: number; element: Element }>
  elementForIndex: (index: number, framePath?: string) => Element | undefined
  selectorFor: (element: Element) => string | undefined
  bindSync: () => void
  placeMark: (label: string, element: Element, color?: string, detail?: string) => void
  scheduleSync: () => void
  runExtract: (
    n: number,
    showHints: boolean
  ) => Promise<{
    report: ExtractReport
    entries: Array<{ index: number; element: Element; title?: string }>
    byIndex: Map<number, Element>
  }>
  reportPayload: (report: ExtractReport) => Record<string, unknown>
  clearMarks: () => void
  selectorEntries: () => Array<{ index: number; element: Element; title?: string }>
  markInViewport: (mark: PageControlMark) => boolean
  watchMarksStale: () => void
  hideCaptureChrome: () => Promise<void>
  restoreCaptureChrome: () => Promise<void>
  performAgentScroll: (payload: Record<string, unknown>) => Promise<{
    scrollY: number
    atBottom: boolean
    target: 'window' | 'inner' | 'none'
    delta: number
  }>
}
