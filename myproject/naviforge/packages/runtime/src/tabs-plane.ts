import type { ToolResult } from '@naviforge/shared'

export type TabSummary = {
  id: number
  url?: string
  title?: string
  active: boolean
  /** Window ownership lets the agent safely transfer focus across browser windows. */
  windowId?: number
}

/** Browser tab plane — implemented in the extension (chrome.tabs). */
export interface TabsPlane {
  list(): Promise<ToolResult<{ tabs: TabSummary[] }>>
  switch(tabId: number): Promise<ToolResult<{ tabId: number }>>
  close(tabId: number): Promise<ToolResult<{ closed: number }>>
  open(url: string): Promise<ToolResult<{ tabId: number }>>
}
