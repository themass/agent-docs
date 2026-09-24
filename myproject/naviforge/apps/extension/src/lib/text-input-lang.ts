/** Typing hygiene only — never set lang / html[lang]; that hijacks Chrome IME on focus. */
export function textInputLangProps(): {
  autoCapitalize: 'off'
  autoCorrect: 'off'
  spellCheck: false
  style: { textTransform: 'none' }
} {
  return {
    autoCapitalize: 'off',
    autoCorrect: 'off',
    spellCheck: false,
    style: { textTransform: 'none' },
  }
}
