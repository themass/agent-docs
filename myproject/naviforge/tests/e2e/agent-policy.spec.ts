import { expect, test } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { evaluateAskUser, resolveTaskScope } from '@naviforge/policy'

test.describe('agent policy', () => {
  test('scoped topN forbids navigation questions only', () => {
    const scope = resolveTaskScope('标记当前页面 top4 视频')
    expect(scope.navigation).toBe('forbidden')
    expect(evaluateAskUser('navigate to 热门', scope).allow).toBe(false)
    expect(evaluateAskUser('请完成验证码', scope).allow).toBe(true)
    expect(evaluateAskUser('需要登录吗？', scope).allow).toBe(true)
  })
})

test.describe('extension build artifact', () => {
  test('chrome mv3 manifest is present after build', () => {
    const manifestPath = resolve(
      import.meta.dirname,
      '../../apps/extension/dist/chrome-mv3/manifest.json'
    )
    test.skip(!existsSync(manifestPath), 'run npm run build first')
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as { manifest_version: number }
    expect(manifest.manifest_version).toBe(3)
  })
})
