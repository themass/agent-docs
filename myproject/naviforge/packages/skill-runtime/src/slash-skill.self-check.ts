import assert from 'node:assert/strict'

import { expandSkillSlashPayload, parseSkillSlashName, skillSlashName } from './slash-skill.ts'
import type { Skill } from './index.ts'

const sample: Skill = {
  manifest: { id: 'demo', version: '1.0.0', description: 'demo skill' },
  instructions: 'Do the thing.',
}

assert.equal(skillSlashName('demo'), 'skill:demo')
assert.equal(parseSkillSlashName('skill:demo'), 'demo')
assert.ok(expandSkillSlashPayload(sample, 'extra').includes('<skill name="demo"'))
assert.ok(expandSkillSlashPayload(sample, 'extra').includes('extra'))
assert.ok(expandSkillSlashPayload(sample, '').includes('Do the thing.'))

console.log('skill-runtime slash-skill self-check ok')
