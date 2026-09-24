export type ComposerEnterIntent = 'send' | 'steer'

export function composerEnterIntent(event: {
  key: string
  shiftKey: boolean
  altKey: boolean
  ctrlKey: boolean
  isComposing: boolean
  keyCode: number
}): ComposerEnterIntent | null {
  if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return null
  if (event.shiftKey) return null
  if (event.ctrlKey) return 'steer'
  return 'send'
}

export function composerIsCompact(state: {
  focused: boolean
  value: string
  hasAttachment: boolean
  listening: boolean
}): boolean {
  return !state.focused && !state.value.trim() && !state.hasAttachment && !state.listening
}

export function shouldSubmitComposer(event: {
  key: string
  shiftKey: boolean
  isComposing: boolean
  keyCode: number
  altKey?: boolean
  ctrlKey?: boolean
}): boolean {
  return (
    composerEnterIntent({
      ...event,
      altKey: event.altKey ?? false,
      ctrlKey: event.ctrlKey ?? false,
    }) === 'send'
  )
}
