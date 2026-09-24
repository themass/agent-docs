/** Wire form: mcp__{server}__{tool} */

const MCP_PREFIX = 'mcp__'
const MCP_DELIM = '__'
const SAFE_BYTE = /^[A-Za-z0-9]$/
const HEX_BYTE = /^[0-9a-f]{2}$/

/** Reversibly encode one UTF-8 MCP name component for provider-safe tool ids. */
export function encodeMcpNameComponent(value: string): string {
  if (!value) throw new Error('MCP name components must not be empty')
  return Array.from(new TextEncoder().encode(value), (byte) => {
    const char = String.fromCharCode(byte)
    return SAFE_BYTE.test(char) ? char : `_${byte.toString(16).padStart(2, '0')}`
  }).join('')
}

function decodeMcpNameComponent(value: string): string | null {
  if (!value) return null
  const bytes: number[] = []
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index]!
    if (SAFE_BYTE.test(char)) {
      bytes.push(char.charCodeAt(0))
      continue
    }
    if (char !== '_' || index + 2 >= value.length) return null
    const hex = value.slice(index + 1, index + 3)
    if (!HEX_BYTE.test(hex)) return null
    bytes.push(Number.parseInt(hex, 16))
    index += 2
  }
  try {
    const decoded = new TextDecoder('utf-8', { fatal: true }).decode(Uint8Array.from(bytes))
    return decoded || null
  } catch {
    return null
  }
}

/** Build registry/wire name: `mcp__{server}__{tool}`. */
export function mcpQualifiedName(serverId: string, toolName: string): string {
  return `${MCP_PREFIX}${encodeMcpNameComponent(serverId)}${MCP_DELIM}${encodeMcpNameComponent(toolName)}`
}

export function isMcpQualifiedToolName(name: string): boolean {
  return parseMcpQualifiedName(name) !== null
}

/** Parse a qualified wire name back to the original raw server and tool names. */
export function parseMcpQualifiedName(
  name: string
): { server: string; tool: string } | null {
  if (!name.startsWith(MCP_PREFIX)) return null
  const rest = name.slice(MCP_PREFIX.length)
  const mid = rest.indexOf(MCP_DELIM)
  if (mid <= 0 || rest.indexOf(MCP_DELIM, mid + MCP_DELIM.length) !== -1) return null
  const server = decodeMcpNameComponent(rest.slice(0, mid))
  const tool = decodeMcpNameComponent(rest.slice(mid + MCP_DELIM.length))
  if (server === null || tool === null) return null
  return { server, tool }
}
