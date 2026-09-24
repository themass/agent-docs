import { jsonrepair } from 'jsonrepair'

function countChar(text: string, ch: string): number {
  let n = 0
  for (const c of text) if (c === ch) n += 1
  return n
}

/** Generate a few brace-balance candidates for common typos like `{{...}` / `{...}}`. */
function braceCandidates(text: string): string[] {
  const out: string[] = [text]
  let open = countChar(text, '{') - countChar(text, '}')
  let cur = text
  while (open > 0 && cur.startsWith('{')) {
    cur = cur.slice(1).trimStart()
    out.push(cur)
    open -= 1
  }
  open = countChar(text, '{') - countChar(text, '}')
  cur = text
  while (open < 0 && cur.endsWith('}')) {
    cur = cur.slice(0, -1).trimEnd()
    out.push(cur)
    open += 1
  }
  return out
}

function parseRepaired(text: string): unknown {
  return JSON.parse(jsonrepair(text))
}

/** Parse leniently: strict JSON first, then jsonrepair (+ brace balance) for broken input. */
export function parseLenient(text: string): { value: unknown; repaired: boolean } {
  const trimmed = text.trim()
  if (!trimmed) throw new Error('内容为空')
  try {
    return { value: JSON.parse(trimmed), repaired: false }
  } catch {
    let lastError: unknown
    for (const candidate of braceCandidates(trimmed)) {
      try {
        return { value: parseRepaired(candidate), repaired: true }
      } catch (error) {
        lastError = error
      }
    }
    throw lastError instanceof Error ? lastError : new Error('无法修复 JSON')
  }
}
