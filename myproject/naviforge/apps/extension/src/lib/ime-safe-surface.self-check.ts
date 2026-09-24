import assert from 'node:assert/strict'

import { shouldPreventFocusSteal } from './ime-safe-surface.js'

function mockEl(
  tag: string,
  opts?: { draggable?: boolean; imeFocusOk?: boolean; chatSelectable?: boolean; composerInput?: boolean }
): HTMLElement {
  const node = {
    closest(selector: string): Element | null {
      if (selector === '[data-chat-selectable]' && opts?.chatSelectable) return node as unknown as Element
      if (selector === '[data-composer-input]' && opts?.composerInput) return node as unknown as Element
      if (selector === '[data-ime-focus-ok]' && opts?.imeFocusOk) return node as unknown as Element
      if (selector === '[draggable="true"]' && opts?.draggable) return node as unknown as Element
      if (selector.includes('textarea') && tag === 'textarea') return node as unknown as Element
      if (selector.includes('input') && tag === 'input') return node as unknown as Element
      if (selector.includes('button') && tag === 'button') return node as unknown as Element
      if (selector.includes('summary') && tag === 'summary') return node as unknown as Element
      return null
    },
  }
  return node as unknown as HTMLElement
}

assert.equal(shouldPreventFocusSteal(mockEl('div', { chatSelectable: true })), false, 'chat text stays selectable')
assert.equal(shouldPreventFocusSteal(mockEl('button')), true, 'buttons should not steal focus')
assert.equal(shouldPreventFocusSteal(mockEl('textarea')), false, 'textarea may take focus')
assert.equal(shouldPreventFocusSteal(mockEl('div', { draggable: true })), false, 'draggable rows need mousedown')

console.log('ime-safe-surface self-check ok')
