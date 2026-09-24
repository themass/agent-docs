import assert from 'node:assert/strict'

import type { SiteProfile } from './content-extract.js'

const disk: Record<string, unknown> = {}
;(globalThis as unknown as { chrome: unknown }).chrome = {
  runtime: { id: 'test-ext' },
  storage: {
    local: {
      get: async (keys: string | string[]) => {
        const key = Array.isArray(keys) ? keys[0]! : keys
        return { [key]: disk[key] }
      },
      set: async (patch: Record<string, unknown>) => {
        Object.assign(disk, patch)
      },
    },
  },
}

// Imported after the storage stub exists, since the module reads chrome at call time.
const { deleteProfile, listLearnedProfiles, listProfiles, rememberProfile, saveProfile } =
  await import('./site-profile-store.js')

const learned: SiteProfile = {
  id: 'learned-video.example.com',
  host: ['video.example.com'],
  detailUrl: '/video/[^/]+',
  source: 'learned',
}

assert.equal(await rememberProfile(undefined), false, 'nothing to learn')
assert.equal(await rememberProfile(learned), true, 'first sighting is stored')
assert.equal((await listLearnedProfiles()).length, 1)

assert.equal(await rememberProfile(learned), false, 'an unchanged profile is not rewritten')
assert.equal(
  await rememberProfile({ ...learned, detailUrl: '/watch/[^/]+' }),
  true,
  'a changed link shape updates the profile'
)
assert.equal((await listLearnedProfiles()).length, 1, 'updates replace instead of appending')

assert.equal(
  await rememberProfile({
    id: 'bilibili-video',
    host: ['bilibili.com'],
    detailUrl: '/nonsense/[^/]+',
    source: 'learned',
  }),
  false,
  'a bundled profile is never overwritten by induction'
)

await saveProfile({ ...learned, detailUrl: '/hand-written/[^/]+', source: 'user' })
assert.equal(
  await rememberProfile({ ...learned, detailUrl: '/machine/[^/]+' }),
  false,
  'a user-authored profile is never overwritten by induction'
)

const resolved = await listProfiles()
assert.equal(resolved[0]?.source, 'user', 'user profiles resolve first')
assert(
  resolved.some((profile) => profile.id === 'bilibili-video'),
  'bundled profiles remain available'
)

await deleteProfile('learned-video.example.com')
assert.equal((await listLearnedProfiles()).length, 0)

console.log('site-profile-store self-check ok')
