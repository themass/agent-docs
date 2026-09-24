/** Heuristic: MCP tools that likely mutate external state need user confirmation. */
const WRITE_TOOL =
  /(?:^|[_-])(create|update|delete|remove|write|send|post|put|patch|insert|upload|destroy|drop|set)(?:$|[_-])/i

export function mcpToolRequiresConfirmation(toolName: string): boolean {
  const name = toolName.trim()
  if (!name) return false
  return WRITE_TOOL.test(name)
}
