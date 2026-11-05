import assert from 'node:assert/strict'

import { routeSkills, type Skill } from './index.js'

const skills: Skill[] = [
  {
    manifest: {
      id: 'observe',
      version: '1.0.0',
      description: '读懂当前页：介绍、总结。非：页外对比、爬取。',
      triggers: ['介绍', '总结'],
    },
    instructions: 'observe body',
  },
  {
    manifest: {
      id: 'media-harvest',
      version: '1.0.0',
      description:
        '抽出媒体播放源。非：介绍、总结、概括、表单、比价、爬取、分页、对比、竞品、github、调研。',
      triggers: ['提取', 'm3u8'],
    },
    instructions: 'media-harvest body',
  },
  {
    manifest: {
      id: 'research',
      version: '1.0.0',
      description: '页外多源对比。非：当前页列表。',
      triggers: ['对比', 'github'],
    },
    instructions: 'research body',
  },
]

const summary = routeSkills('请介绍一下这个页面', skills, 3)
assert.equal(summary[0]?.manifest.id, 'observe')
assert.ok(!summary.some((s) => s.manifest.id === 'media-harvest'), 'media-harvest excluded by 介绍')

const boosted = routeSkills('请分析一下这个页面内容', skills, 3, {
  preferredSkillIds: ['media-harvest'],
})
assert.equal(boosted[0]?.manifest.id, 'media-harvest')

const media = routeSkills('给我 m3u8 播放地址', skills, 2)
assert.equal(media[0]?.manifest.id, 'media-harvest')

console.log('route-skills.self-check ok')
