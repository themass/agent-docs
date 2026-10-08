const BUILTIN_TOOL_ID = /^[a-z][a-z0-9_]*$/;
export class ToolRegistry {
    #handlers = new Map();
    register(id, handler) {
        if (!BUILTIN_TOOL_ID.test(id) || id.startsWith('mcp__')) {
            throw new Error(`invalid builtin tool id: ${id}`);
        }
        if (this.#handlers.has(id))
            throw new Error(`duplicate tool handler: ${id}`);
        this.#handlers.set(id, handler);
        return this;
    }
    ids() {
        return [...this.#handlers.keys()];
    }
    get(id) {
        return this.#handlers.get(id);
    }
    assertCatalog(catalogIds) {
        const missing = catalogIds.filter((id) => !this.#handlers.has(id));
        if (missing.length) {
            throw new Error(`tool registry missing catalog handlers: [${missing.join(', ')}]`);
        }
    }
}
