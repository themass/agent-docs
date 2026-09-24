import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { createTraceRecord } from '@naviforge/session'

import {
  dispatchWorkspace,
  ensureWorkspace,
  fileManagerCommand,
  parseSkillMarkdown,
  registerNativeHost,
  resolveSafe,
  sessionFileName,
} from './workspace.js'
import { globToRegExp } from './fs-ops.js'

assert.ok(globToRegExp('**/*.md').test('skills/demo/SKILL.md'))
assert.ok(globToRegExp('**/*.md').test('README.md'))
assert.ok(!globToRegExp('**/*.md').test('shots/a.png'))

assert.equal(resolveSafe('/tmp/ws', 'shots/a.png'), path.resolve('/tmp/ws/shots/a.png'))
assert.throws(() => resolveSafe('/tmp/ws', '../etc/passwd'), /escapes/)
assert.throws(() => resolveSafe('/tmp/ws', '/etc/passwd'), /escapes/)
assert.throws(() => resolveSafe('/tmp/ws', 'shots/../../etc/passwd'), /escapes/)
await assert.rejects(registerNativeHost('/tmp/ws', 'not-an-id'), /invalid Chrome extension id/)

const parsed = parseSkillMarkdown(`---
name: Foo Bar
description: hello
version: 1.2.3
triggers: a, b
---

Do the thing.
`)
assert.equal(parsed.id, 'foo-bar')
assert.equal(parsed.version, '1.2.3')
assert.equal(parsed.instructions, 'Do the thing.')
assert.deepEqual(parsed.triggers, ['a', 'b'])
assert.equal(parsed.enabled, true)

const disabled = parseSkillMarkdown(`---
id: off
description: x
enabled: false
---

body
`)
assert.equal(disabled.enabled, false)

assert.equal(sessionFileName('abc-123', '截图在哪了'), 'abc-123-截图在哪了.jsonl')
assert.equal(fileManagerCommand('darwin'), 'open')
assert.equal(fileManagerCommand('win32'), 'explorer')
assert.equal(fileManagerCommand('linux'), 'xdg-open')

const root = await mkdtemp(path.join(tmpdir(), 'naviforge-ws-'))
try {
  await ensureWorkspace(root)
  await dispatchWorkspace(root, {
    op: 'writeSkill',
    id: 'demo',
    markdown: '---\nname: demo\ndescription: disk skill\n---\n\nUse this.\n',
  })
  const scanned = (await dispatchWorkspace(root, { op: 'scanSkills' })) as {
    skills: Array<{ id: string; enabled: boolean }>
  }
  assert.ok(scanned.skills.length === 1)
  assert.equal(scanned.skills[0]?.id, 'demo')
  assert.equal(scanned.skills[0]?.enabled, true)

  await dispatchWorkspace(root, {
    op: 'write',
    path: 'skills/demo/scripts/run.py',
    content: 'print("ok")\n',
  })
  await dispatchWorkspace(root, {
    op: 'write',
    path: 'skills/demo/references/api.md',
    content: '# api\n',
  })
  const withFiles = (await dispatchWorkspace(root, { op: 'scanSkills' })) as {
    skills: Array<{ files?: string[] }>
  }
  assert.deepEqual(
    withFiles.skills[0]?.files,
    ['skills/demo/references/api.md', 'skills/demo/scripts/run.py'],
  )

  await dispatchWorkspace(root, { op: 'setSkillDisabled', id: 'demo', disabled: true })
  const after = (await dispatchWorkspace(root, { op: 'scanSkills' })) as {
    skills: Array<{ enabled: boolean }>
  }
  assert.equal(after.skills[0]?.enabled, false)

  const png =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  const shot = (await dispatchWorkspace(root, {
    op: 'shot',
    kind: 'visible',
    dataUrl: png,
    threadId: 'thread-1',
    slug: 'hello',
    title: 'hello',
    runId: 'run-1',
  })) as { relativePath: string }
  assert.match(shot.relativePath, /^shots\/.+\.png$/)
  const roundtrip = (await dispatchWorkspace(root, {
    op: 'readDataUrl',
    path: shot.relativePath,
  })) as { dataUrl: string }
  assert.ok(roundtrip.dataUrl.startsWith('data:image/png;base64,'))
  assert.equal(
    Buffer.from(roundtrip.dataUrl.slice(roundtrip.dataUrl.indexOf(',') + 1), 'base64').equals(
      Buffer.from(png.slice(png.indexOf(',') + 1), 'base64')
    ),
    true
  )
  await dispatchWorkspace(root, { op: 'write', path: 'shots/bad.svg', content: '<svg></svg>' })
  await assert.rejects(dispatchWorkspace(root, { op: 'readDataUrl', path: 'shots/bad.svg' }), /not an image/)
  await assert.rejects(dispatchWorkspace(root, { op: 'readDataUrl', path: 'README.md' }), /not an image/)
  await dispatchWorkspace(root, { op: 'touch', path: 'shots/empty.png' })
  await assert.rejects(dispatchWorkspace(root, { op: 'readDataUrl', path: 'shots/empty.png' }), /empty/)

  const webm = 'data:audio/webm;codecs=opus;base64,AAAA'
  const clip = (await dispatchWorkspace(root, {
    op: 'audio',
    kind: 'voice',
    dataUrl: webm,
  })) as { relativePath: string }
  assert.match(clip.relativePath, /^audio\/.+\.webm$/)
  const audioRoundtrip = (await dispatchWorkspace(root, {
    op: 'readDataUrl',
    path: clip.relativePath,
  })) as { dataUrl: string }
  assert.ok(audioRoundtrip.dataUrl.startsWith('data:audio/webm;base64,'))
  await assert.rejects(dispatchWorkspace(root, { op: 'audio', dataUrl: png }), /expected audio/)

  const pageMd = (await dispatchWorkspace(root, {
    op: 'page',
    kind: 'md',
    slug: 'Hello World',
    content: '# Hello\n\nSource: https://example.com\n\nbody\n',
  })) as { relativePath: string; bytes: number }
  assert.match(pageMd.relativePath, /^pages\/.+\.md$/)
  assert.ok(pageMd.bytes > 10)
  const writtenMd = await readFile(path.join(root, pageMd.relativePath), 'utf8')
  assert.ok(writtenMd.includes('# Hello'))
  await assert.rejects(dispatchWorkspace(root, { op: 'page', kind: 'md', content: '   ' }), /empty markdown/)

  const pdfBytes = Buffer.from('%PDF-1.4\n%\n')
  const pagePdf = (await dispatchWorkspace(root, {
    op: 'page',
    kind: 'pdf',
    slug: 'Hello',
    dataUrl: `data:application/pdf;base64,${pdfBytes.toString('base64')}`,
  })) as { relativePath: string; bytes: number }
  assert.match(pagePdf.relativePath, /^pages\/.+\.pdf$/)
  assert.equal(pagePdf.bytes, pdfBytes.length)
  assert.ok((await readFile(path.join(root, pagePdf.relativePath))).equals(pdfBytes))
  await assert.rejects(dispatchWorkspace(root, { op: 'page', kind: 'pdf', dataUrl: png }), /expected pdf/)
  await assert.rejects(dispatchWorkspace(root, { op: 'page', kind: 'gif' }), /kind must be md or pdf/)

  const session = (await dispatchWorkspace(root, {
    op: 'append',
    threadId: 'thread-1',
    slug: 'hello',
    line: createTraceRecord({ type: 'user.task', runId: 'run-1', payload: { text: 'hi' } }),
  })) as { relativePath: string }
  assert.equal(session.relativePath, 'sessions/thread-1-hello.jsonl')
  const jsonl = await readFile(path.join(root, session.relativePath), 'utf8')
  const lines = jsonl.trim().split('\n').map((line) => JSON.parse(line) as { record?: string; type?: string })
  assert.ok(lines.every((line) => !line.record), 'session JSONL contains only canonical records')
  assert.ok(lines.some((line) => line.type === 'artifact.saved'))
  assert.ok(lines.some((line) => line.type === 'user.task'))

  await dispatchWorkspace(root, {
    op: 'writeMcp',
    connections: [
      {
        id: 'fetch',
        name: 'Fetch',
        transport: 'stdio',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-fetch'],
        enabled: true,
        allowedTools: ['*'],
      },
    ],
  })
  const mcp = (await dispatchWorkspace(root, { op: 'readMcp' })) as {
    connections: Array<{ id: string; command?: string }>
    text: string
    format: string
  }
  assert.equal(mcp.connections.length, 1)
  assert.equal(mcp.format, 'cursor')
  assert.ok(mcp.text.includes('"mcpServers"'))
  assert.equal(mcp.connections[0]?.command, 'npx')
  const raw = await readFile(path.join(root, 'mcp/servers.json'), 'utf8')
  assert.ok(JSON.parse(raw).mcpServers.fetch)

  await dispatchWorkspace(root, {
    op: 'writeMcpText',
    text: JSON.stringify({
      mcpServers: {
        docs: { url: 'http://127.0.0.1:9/mcp', headers: { Authorization: 'Bearer x' } },
      },
    }),
  })
  const remote = (await dispatchWorkspace(root, { op: 'readMcp' })) as {
    connections: Array<{ id: string; headers?: Record<string, string> }>
  }
  assert.equal(remote.connections[0]?.id, 'docs')
  assert.equal(remote.connections[0]?.headers?.Authorization, 'Bearer x')

  const invalid = (await dispatchWorkspace(root, {
    op: 'validateMcp',
    text: '{"mcpServers":{"x":{"command":"npx","url":"http://127.0.0.1/mcp"}}}',
  })) as { issues: Array<{ level: string }> }
  assert.ok(invalid.issues.some((issue) => issue.level === 'error'))

  await dispatchWorkspace(root, { op: 'write', path: 'shots/nested/deep.png', content: 'png' })
  const nestedList = (await dispatchWorkspace(root, { op: 'list', dir: 'shots', recursive: true })) as {
    entries: Array<{ name: string; kind: string; mtime?: number }>
  }
  assert.ok(
    nestedList.entries.some((entry) => entry.name === 'nested/deep.png' && entry.kind === 'file'),
    'recursive list includes nested shot'
  )
  assert.ok(
    nestedList.entries.some((entry) => typeof entry.mtime === 'number' && entry.mtime > 0),
    'list entries include mtime'
  )
  await rm(path.join(root, 'audio'), { recursive: true, force: true })
  const missingAudio = (await dispatchWorkspace(root, { op: 'list', dir: 'audio' })) as {
    entries: unknown[]
  }
  assert.deepEqual(missingAudio.entries, [], 'missing workspace dir lists as empty')
  const shotsAfterAudioGone = (await dispatchWorkspace(root, {
    op: 'list',
    dir: 'shots',
    recursive: true,
  })) as { entries: Array<{ name: string }> }
  assert.ok(
    shotsAfterAudioGone.entries.some((entry) => entry.name === 'nested/deep.png'),
    'list shots still works after a sibling dir is missing'
  )

  await dispatchWorkspace(root, { op: 'writeScript', filename: 'demo.py', content: 'print(1)\n' })
  const listed = (await dispatchWorkspace(root, { op: 'list', dir: 'scripts' })) as {
    entries: Array<{ name: string }>
  }
  assert.ok(listed.entries.some((entry) => entry.name === 'demo.py'))

  await dispatchWorkspace(root, { op: 'mkdir', path: 'scripts/nested' })
  await dispatchWorkspace(root, { op: 'touch', path: 'scripts/nested/empty.txt' })
  const touched = (await dispatchWorkspace(root, { op: 'stat', path: 'scripts/nested/empty.txt' })) as {
    kind: string
    size: number
  }
  assert.equal(touched.kind, 'file')
  assert.equal(touched.size, 0)

  const globbed = (await dispatchWorkspace(root, { op: 'glob', pattern: '**/*.md' })) as { paths: string[] }
  assert.ok(globbed.paths.includes('skills/demo/SKILL.md'))
  const grepped = (await dispatchWorkspace(root, {
    op: 'grep',
    pattern: 'Use this',
    glob: '**/*.md',
  })) as { hits: Array<{ path: string; line: number }> }
  assert.ok(grepped.hits.some((hit) => hit.path === 'skills/demo/SKILL.md'))

  await dispatchWorkspace(root, {
    op: 'write',
    path: 'config/models.json',
    content: JSON.stringify({ version: 1, profiles: [] }, null, 2),
  })
  const modelsMode = (await stat(path.join(root, 'config/models.json'))).mode & 0o777
  assert.equal(modelsMode, 0o600)

  const jsonlKeys = jsonl.trim().split('\n').map((line) => Object.keys(JSON.parse(line) as object))
  assert.equal(jsonlKeys[0]?.[0], 'schema')
  assert.equal(jsonlKeys[0]?.[1], 'id')

  await dispatchWorkspace(root, { op: 'clearDir', dir: 'scripts' })
  const cleared = (await dispatchWorkspace(root, { op: 'list', dir: 'scripts' })) as {
    entries: Array<{ name: string }>
  }
  assert.equal(cleared.entries.length, 0)
  await assert.rejects(dispatchWorkspace(root, { op: 'clearDir', dir: 'skills' }), /only allows/)
} finally {
  await rm(root, { recursive: true, force: true })
}

console.log('host workspace self-check ok')
