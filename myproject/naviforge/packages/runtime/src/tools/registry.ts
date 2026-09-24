export type ToolHandler<TContext, TResult> = (context: TContext) => Promise<TResult> | TResult

const BUILTIN_TOOL_ID = /^[a-z][a-z0-9_]*$/

export class ToolRegistry<TContext, TResult> {
  readonly #handlers = new Map<string, ToolHandler<TContext, TResult>>()

  register(id: string, handler: ToolHandler<TContext, TResult>): this {
    if (!BUILTIN_TOOL_ID.test(id) || id.startsWith('mcp__')) {
      throw new Error(`invalid builtin tool id: ${id}`)
    }
    if (this.#handlers.has(id)) throw new Error(`duplicate tool handler: ${id}`)
    this.#handlers.set(id, handler)
    return this
  }

  ids(): string[] {
    return [...this.#handlers.keys()]
  }

  get(id: string): ToolHandler<TContext, TResult> | undefined {
    return this.#handlers.get(id)
  }

  assertCatalog(catalogIds: readonly string[]): void {
    const missing = catalogIds.filter((id) => !this.#handlers.has(id))
    if (missing.length) {
      throw new Error(`tool registry missing catalog handlers: [${missing.join(', ')}]`)
    }
  }
}
