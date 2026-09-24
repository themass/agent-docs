/** One native function call selected by the model for a loop iteration. */
export type ToolCall = {
  tool: string
  arguments: Record<string, unknown>
}

export type ToolResult<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string; recoverable: boolean } }
