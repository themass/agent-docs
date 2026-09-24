/** Structured turn messages for prompt compilation (pi-style, lightweight). */
export type TurnMessage = {
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
}

export function traceLinesToMessages(lines: string[]): TurnMessage[] {
  return lines.map((line) => {
    if (line.startsWith('USER CORRECTION:')) return { role: 'user', content: line }
    if (line.startsWith('USER ANSWER:')) return { role: 'user', content: line }
    if (line.startsWith('FOLLOW-UP:')) return { role: 'user', content: line }
    if (line.includes(' fail ')) return { role: 'tool', content: line }
    if (line.startsWith('ask:') || line.startsWith('done:')) {
      return { role: 'assistant', content: line }
    }
    return { role: 'tool', content: line }
  })
}

export function formatMessagesForPrompt(messages: TurnMessage[], limit = 8): string {
  const recent = messages.slice(-limit)
  if (!recent.length) return '(none)'
  return recent.map((message) => `[${message.role}] ${message.content}`).join('\n')
}
