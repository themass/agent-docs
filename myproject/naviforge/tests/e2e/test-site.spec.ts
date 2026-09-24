import { expect, test } from '@playwright/test'
import { resolveHlsPlaylist } from '@naviforge/media-plane'

test.describe('demos/test-site', () => {
  test('phase 0: type and click shows Success', async ({ page }) => {
    await page.goto('/')
    await page.getByPlaceholder('type here').fill('hello')
    await page.getByRole('button', { name: 'Go' }).click()
    await expect(page.locator('#out')).toHaveText('Success: hello')
  })

  test('phase C: iframe button works', async ({ page }) => {
    await page.goto('/')
    const frame = page.frameLocator('iframe')
    await frame.getByRole('button', { name: 'Frame Go' }).click()
    await expect(frame.locator('#frame-out')).toHaveText('Frame Success')
  })

  test('phase C: open shadow exposes link text', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Demo Video 1')).toBeVisible()
  })

  test('fake API json list is fetchable', async ({ request }) => {
    const response = await request.get('/fake/api/videos.json')
    expect(response.ok()).toBeTruthy()
    const json = (await response.json()) as { items: Array<{ title: string }> }
    expect(json.items[0]?.title).toBe('Demo Video 1')
  })

  test('master m3u8 resolves variants and segments', async ({ request }) => {
    const master = await request.get('/fake/master.m3u8')
    expect(master.ok()).toBeTruthy()
    const text = await master.text()
    const parsed = resolveHlsPlaylist(text, 'http://127.0.0.1:4177/fake/master.m3u8')
    expect(parsed.kind).toBe('master')
    expect(parsed.variants.length).toBeGreaterThanOrEqual(2)

    const media = await request.get('/fake/720p/index.m3u8')
    const mediaText = await media.text()
    const segments = resolveHlsPlaylist(
      mediaText,
      'http://127.0.0.1:4177/fake/720p/index.m3u8'
    )
    expect(segments.kind).toBe('media')
    expect(segments.segments.some((url) => url.includes('seg-001.ts'))).toBeTruthy()
  })
})
