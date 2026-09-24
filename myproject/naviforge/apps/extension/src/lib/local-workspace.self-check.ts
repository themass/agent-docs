import assert from 'node:assert/strict'

import { formatWorkspaceMtime, loadWorkspaceFileLists, skillToMarkdown, workspaceEmptyHint } from './local-workspace'
import { mergeInstalledSkills } from './settings'
import type { WorkspaceEntry } from '@naviforge/runtime'
import type { Skill } from '@naviforge/skill-runtime'

const skill: Skill = {
  manifest: { id: 'demo', version: '1.0.0', description: 'disk', triggers: ['foo'] },
  instructions: 'Do it.',
}
const md = skillToMarkdown(skill)
assert.ok(md.includes('name: demo'))
assert.ok(md.includes('Do it.'))

const bundled: Skill[] = [
  { manifest: { id: 'page-read', version: '0.1.0', description: 'bundled' }, instructions: 'b' },
]
const custom: Skill[] = [
  { manifest: { id: 'page-read', version: '9.0.0', description: 'override' }, instructions: 'c' },
  { manifest: { id: 'local', version: '0.0.1', description: 'disk' }, instructions: 'd' },
]
const merged = mergeInstalledSkills(bundled, custom)
assert.equal(merged.find((item) => item.manifest.id === 'page-read')?.manifest.version, '9.0.0')
assert.ok(merged.some((item) => item.manifest.id === 'local'))

const file = (name: string): WorkspaceEntry => ({ name, kind: 'file', mtime: 1 })
const isolated = await loadWorkspaceFileLists(['shots', 'audio', 'pages'], async (dir) => {
  if (dir === 'audio') throw new Error('Host HTTP 400')
  if (dir === 'shots') return [file('nested/deep.png')]
  return []
})
assert.equal(isolated.lists.shots?.[0]?.name, 'nested/deep.png', 'sibling shots survive a throwing dir')
assert.deepEqual(isolated.lists.pages, [])
assert.ok(isolated.errors.some((item) => item.startsWith('audio:')), 'failed dir is reported')

const swallowed = await loadWorkspaceFileLists(['audio', 'shots'], async (dir) => {
  if (dir === 'audio') return []
  return [file('a.png')]
})
assert.equal(swallowed.errors.length, 0)
assert.equal(swallowed.lists.shots?.length, 1)

assert.equal(workspaceEmptyHint(null, '还没有截图。'), '正在连接本机助手…')
assert.match(workspaceEmptyHint(false, '还没有截图。'), /本机助手未连接/)
assert.doesNotMatch(workspaceEmptyHint(false, '还没有截图。'), /^还没有截图/)
assert.equal(workspaceEmptyHint(true, '还没有截图。'), '还没有截图。')

assert.equal(formatWorkspaceMtime(undefined), '')
assert.equal(formatWorkspaceMtime(0), '')
assert.match(formatWorkspaceMtime(Date.parse('2026-08-15T11:19:00')), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)

console.log('local-workspace self-check ok')
