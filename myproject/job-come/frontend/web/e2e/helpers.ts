import { expect, test, type Page } from "@playwright/test";

export const EMAIL = process.env.JC_E2E_EMAIL ?? "metrics-probe-20261114@example.com";
export const PASSWORD = process.env.JC_E2E_PASSWORD ?? "";

export const HAS_CREDENTIALS = PASSWORD.length > 0;

/** The password field, not the "show password" button that also matches 密码. */
export function passwordInput(page: Page) {
  return page.locator('input[type="password"]').first();
}

export function emailInput(page: Page) {
  // The email field is the first text-ish input on the form; labelling is
  // inconsistent between the login and register pages.
  return page.locator('input[type="email"], input[autocomplete="username"]').first();
}

/**
 * Return `value`, or skip the test when it is absent.
 *
 * `test.skip(cond, why)` returns void, so TypeScript cannot narrow anything after
 * it and every call site needs an assertion. Putting it here keeps the claim in
 * one place ("after this line it exists") instead of eight.
 */
export function requireValue<T>(value: T | undefined | null, reason: string): T {
  if (value === undefined || value === null) test.skip(true, reason);
  return value as T;
}

/**
 * Ensure the page has a signed-in session.
 *
 * Normally `global-setup.ts` already logged in and its `storageState` is loaded,
 * so this only has to confirm it. That matters: with 36 tests each driving the
 * form, one login timed out mid-run and the export test failed with "still on
 * /auth/login" — an export failure that was really a login flake.
 *
 * The form path stays, and `a-auth.spec.ts` still exercises it for real: that is
 * the suite which asserts the form works. Logging in by injecting a cookie for
 * every test would make a broken login form invisible everywhere else.
 */
export async function login(page: Page): Promise<void> {
  await page.goto("/auth/account");
  const url = page.url();
  const body = await page.locator("body").innerText();

  // Already signed in: the account page rendered instead of redirecting away.
  if (!/\/auth\/login/.test(url) && !/请先登录|登录后可/.test(body)) return;

  await page.goto("/auth/login");
  await emailInput(page).fill(EMAIL);
  await passwordInput(page).fill(PASSWORD);
  await page.locator('form button[type="submit"]').first().click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 40_000 });
}

/**
 * A confirmed profile that is guaranteed to have one evidence gap.
 *
 * `evidence_gaps` raises `vague_quantity` for a bullet containing 「多项」 with no
 * metric in it — read from `services/evidence_gaps.py`, not guessed. Existing
 * profiles on the test account had no gaps, so the gap-dependent cases skipped on
 * every run; a skip that always fires is a case that is never verified.
 */
export async function seedProfileWithGap(page: Page): Promise<{ id: string } | undefined> {
  const created = await page.request.post(
    new URL("/api/v1/profiles", page.url()).toString(),
    { data: { name: `e2e-gap-${Date.now()}` } },
  );
  if (created.status() >= 400) return undefined;
  const prof = await created.json();

  const seeded = await page.request.patch(
    new URL(`/api/v1/profiles/${prof.id}`, page.url()).toString(),
    {
      data: {
        payload: {
          contact: { name: "缺口验证", email: "gap@example.com" },
          summary: "后端工程师，负责高并发系统。",
          experiences: [
            {
              id: "exp_gap1",
              company: "示例科技",
              title: "后端工程师",
              start_date: "2021-03",
              end_date: "",
              scope: "负责订单系统",
              // Three highlights because `profile_intake` refuses generation below
              // `_MIN_VIABLE_HIGHLIGHTS = 3` — a 409 that reads as "cannot generate"
              // and sent this test down the wrong path for a while. Only the first
              // one carries 「多项」; the other two are ordinary so the fixture stays
              // about the gap rather than about filling the floor.
              highlights: [
                "参与优化了多项核心接口的响应速度",
                "把订单查询 P99 从 820ms 降到 130ms，日均请求 3000 万",
                "主导拆分单体订单服务，故障隔离后可用性从 99.5% 提升到 99.95%",
              ],
              skills: ["Go"],
            },
          ],
        },
      },
    },
  );
  if (seeded.status() >= 400) return undefined;

  const confirmed = await page.request.post(
    new URL(`/api/v1/profiles/${prof.id}/confirm`, page.url()).toString(),
    { data: {} },
  );
  if (confirmed.status() >= 400) return undefined;

  // Activate first. `/resume-agent` renders the *active* profile, not the newest
  // row, so generating a draft for a different profile leaves the page with nothing
  // to show — which is why the anchor cases kept skipping.
  // No request body: `activate_profile` takes only the path parameter.
  const activated = await page.request.post(
    new URL(`/api/v1/profiles/${prof.id}/activate`, page.url()).toString(),
  );
  if (activated.status() >= 400) return undefined;

  // Generate the optimized draft: it is what the structured view renders and
  // therefore what carries `data-path` anchors.
  //
  // This can legitimately answer 409 `preview_profile_changed`: confirming a
  // profile queues `prepare_resume_tracks` in the background, which bumps the
  // version while the preview is being produced, and the guard refuses to show a
  // draft computed from a stale version. That is the correct behaviour — the retry
  // is what a real client does, not a workaround.
  const previewUrl = new URL(
    `/api/v1/profiles/${prof.id}/elevate/preview?elevation_level=standard&locale=zh-CN`,
    page.url(),
  ).toString();

  for (let attempt = 0; attempt < 3; attempt++) {
    const preview = await page.request.get(previewUrl, { timeout: 300_000 });
    if (preview.status() < 400) return { id: prof.id };

    const body = await preview.text();
    if (!/preview_profile_changed/.test(body)) return undefined;
    await page.waitForTimeout(2000);
  }
  return undefined;
}
