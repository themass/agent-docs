const NAMED_KEYS: Record<string, { key: string; code: string }> = {
  Enter: { key: 'Enter', code: 'Enter' },
  Escape: { key: 'Escape', code: 'Escape' },
  Tab: { key: 'Tab', code: 'Tab' },
  Backspace: { key: 'Backspace', code: 'Backspace' },
  Delete: { key: 'Delete', code: 'Delete' },
  ArrowUp: { key: 'ArrowUp', code: 'ArrowUp' },
  ArrowDown: { key: 'ArrowDown', code: 'ArrowDown' },
  ArrowLeft: { key: 'ArrowLeft', code: 'ArrowLeft' },
  ArrowRight: { key: 'ArrowRight', code: 'ArrowRight' },
  ' ': { key: ' ', code: 'Space' },
  Space: { key: ' ', code: 'Space' },
}

export function simulateKeyPress(
  target: HTMLElement,
  key: string,
  modifiers: string[] = []
): void {
  const mapped = NAMED_KEYS[key] ?? { key, code: key.length === 1 ? `Key${key.toUpperCase()}` : key }
  const mod = {
    ctrlKey: modifiers.includes('ctrl') || modifiers.includes('control'),
    altKey: modifiers.includes('alt'),
    shiftKey: modifiers.includes('shift'),
    metaKey: modifiers.includes('meta') || modifiers.includes('cmd') || modifiers.includes('command'),
  }
  const sequence: Array<'keydown' | 'keypress' | 'keyup'> = ['keydown', 'keypress', 'keyup']
  for (const type of sequence) {
    target.dispatchEvent(
      new KeyboardEvent(type, {
        ...mod,
        key: mapped.key,
        code: mapped.code,
        bubbles: true,
        cancelable: true,
      })
    )
  }
}
