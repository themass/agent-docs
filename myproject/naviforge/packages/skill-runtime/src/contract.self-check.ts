import { findSkill, resolveCanonicalSkill, type Skill } from './index.js'

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

const versions: Skill[] = [
  {
    manifest: { id: 'demo', version: '1.0.0', description: 'old' },
    instructions: 'old',
  },
  {
    manifest: { id: 'demo', version: '2.0.0', description: 'new' },
    instructions: 'new',
  },
  {
    manifest: {
      id: 'demo-alias',
      version: '1.0.0',
      description: 'alias',
      aliasOf: 'demo',
      l1: false,
    },
    instructions: 'alias',
  },
]

assert(findSkill(versions, 'demo@2.0.0')?.manifest.version === '2.0.0', 'versioned skill resolves exactly')
assert(findSkill(versions, 'demo@9.9.9') === undefined, 'missing skill version does not silently fall back')
assert(resolveCanonicalSkill(versions, 'demo-alias')?.manifest.id === 'demo', 'skill alias resolves canonical skill')

console.log('skill contract self-check: ok')
