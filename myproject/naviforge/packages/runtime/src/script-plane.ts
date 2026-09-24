import type { ToolResult } from '@naviforge/shared'

export type ScriptLanguage = 'python' | 'shell' | 'javascript'

/** Durable script artifact, saved separately from extension Playbooks. */
export type ScriptArtifact = {
  id: string
  title: string
  language: ScriptLanguage
  filename: string
  content: string
  createdAt: number
  updatedAt: number
  sourceUrl?: string
}

/** User-directed script persistence/export boundary. */
export interface ScriptPlane {
  save(opts: {
    title: string
    language: ScriptLanguage
    filename: string
    content: string
    sourceUrl?: string
  }): Promise<ToolResult<{ id: string; filename: string }>>
  download(id: string): Promise<ToolResult<{ downloadId: number }>>
}
