/** Strip pseudo-instruction patterns from untrusted page/tool text before prompt injection. */
export function sanitizeUntrustedText(
  text: string,
  opts?: { maxChars?: number; label?: string }
): string {
  const max = opts?.maxChars ?? 8_000
  let s = text.replace(/\r\n/g, '\n')
  s = s.replace(/<\/?system>/gi, '')
  s = s.replace(/^(CONSTRAINT|GUIDANCE|SYSTEM):/gim, '[untrusted]:')
  if (s.length > max) {
    s = `${s.slice(0, max)}\n… (truncated)`
  }
  return s
}
