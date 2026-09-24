import assert from 'node:assert/strict'

import { htmlToMarkdown, wrapPageMarkdown } from './page-markdown'

const md = htmlToMarkdown('<h1>Hello</h1><p>a <strong>b</strong> and <em>c</em></p>')
assert.match(md, /# Hello/)
assert.match(md, /\*\*b\*\*/)
assert.match(md, /[_*]c[_*]/)

const wrapped = wrapPageMarkdown('Title', 'https://example.com/x', 'body')
assert.ok(wrapped.startsWith('# Title\n'))
assert.ok(wrapped.includes('Source: https://example.com/x'))
assert.ok(wrapped.includes('body'))

const skipped = htmlToMarkdown('<p>keep</p><img src="data:image/png;base64,AAAA" alt="x">')
assert.ok(skipped.includes('keep'))
assert.ok(!skipped.includes('data:image'))

console.log('page-markdown self-check ok')
