import { expect, test, type APIRequestContext, type Page, type PlaywrightWorkerArgs } from "@playwright/test";
import { EMAIL, HAS_CREDENTIALS, PASSWORD, login } from "./helpers";

/**
 * M-01~M-04: one account must not reach another's data.
 *
 * This needs two real accounts, which is why it was listed as a gap: asserting
 * "my own data loads" proves nothing about isolation. The fixture logs in as A,
 * opens a *separate* request context as B, and tries to read A's resources with
 * B's own session cookie — so the refusal, if it happens, comes from the
 * ownership guard rather than from a missing cookie.
 */

const B_EMAIL = process.env.JC_E2E_EMAIL_B ?? "e2e-probe-b-20261115@example.com";
const B_PASSWORD = process.env.JC_E2E_PASSWORD_B ?? "";
const HAS_BOTH = HAS_CREDENTIALS && B_PASSWORD.length > 0;

async function firstProfileId(page: Page): Promise<string | undefined> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  return list[0]?.id;
}

/**
 * A request context authenticated as B, with its own cookie jar.
 *
 * Built from the `playwright` fixture rather than `page.request`, which is itself
 * already a context and has no `newContext()`. Sharing the page's jar would make
 * every assertion vacuous: the cookie would be A's, so "B was refused" and "B saw
 * nothing" would both be true for the wrong reason.
 */
async function contextAsB(playwright: PlaywrightWorkerArgs["playwright"], base: string) {
  const ctx = await playwright.request.newContext();
  const res = await ctx.post(`${base}/api/v1/auth/login`, {
    data: { email: B_EMAIL, password: B_PASSWORD },
  });
  expect(res.status(), "B 账号登录失败，隔离用例无法进行").toBe(200);
  return ctx;
}

/** B asking for something that belongs to A must be refused, or must not match. */
async function expectRefused(
  ctx: APIRequestContext,
  base: string,
  path: string,
  label: string,
): Promise<void> {
  const res = await ctx.get(`${base}${path}`);
  if (res.status() === 200) {
    const text = await res.text();
    // A 200 is only acceptable when the payload is genuinely empty — a list of
    // zero items is a fine answer to "someone else's profiles"; the leak is data.
    expect(text, `${label}：B 读到了 A 的数据`).toMatch(/^(\{"(profiles|sessions|calls)":\[\]\}|\[\])$/);
    return;
  }
  expect([400, 403, 404], `${label}：返回了 ${res.status()}`).toContain(res.status());
}

test.describe("M. 跨用户隔离", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_BOTH, "需要 JC_E2E_PASSWORD 与 JC_E2E_PASSWORD_B 两个账号");
    await login(page);
  });

  test("M-01 B 读不到 A 的档案", async ({ page, playwright }) => {
    const base = new URL(page.url()).origin;
    const ctx = await contextAsB(playwright, base);
    const pid = await firstProfileId(page);
    test.skip(!pid, "A 账号没有档案");

    await expectRefused(ctx, base, `/api/v1/profiles/${pid}`, "M-01 档案详情");
    await ctx.dispose();
  });

  test("M-01b A 的档案不出现在 B 的列表里", async ({ page, playwright }) => {
    const base = new URL(page.url()).origin;
    const ctx = await contextAsB(playwright, base);
    const pid = await firstProfileId(page);
    test.skip(!pid, "A 账号没有档案");

    const res = await ctx.get(`${base}/api/v1/profiles`);
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text, "B 的档案列表里出现了 A 的档案").not.toContain(pid);
    await ctx.dispose();
  });

  test("M-02 B 读不到 A 的 agent 会话", async ({ page, playwright }) => {
    const base = new URL(page.url()).origin;
    const ctx = await contextAsB(playwright, base);
    const pid = await firstProfileId(page);
    test.skip(!pid, "A 账号没有档案");

    const listRes = await page.request.get(
      new URL(`/api/v1/agent/sessions?profile_id=${pid}`, page.url()).toString(),
    );
    if (listRes.status() !== 200) return;
    const list = await listRes.json();
    const sessions = Array.isArray(list) ? list : (list.sessions ?? []);
    const sid = sessions[0]?.id;
    test.skip(!sid, "A 账号没有会话");

    await expectRefused(ctx, base, `/api/v1/agent/sessions/${sid}`, "M-02 会话详情");
    await expectRefused(ctx, base, `/api/v1/agent/sessions/${sid}/messages`, "M-02 会话消息");
    await ctx.dispose();
  });

  test("M-04 B 读不到 A 的简历版本", async ({ page, playwright }) => {
    const base = new URL(page.url()).origin;
    const ctx = await contextAsB(playwright, base);
    const pid = await firstProfileId(page);
    test.skip(!pid, "A 账号没有档案");

    const res = await ctx.get(`${base}/api/v1/resume-versions?profile_id=${pid}`);
    if (res.status() === 200) {
      // The property is "A's versions never reach B", not "B has no versions at all".
      // The earlier assertion required every group to be empty, so it failed the moment
      // B generated a draft of its own — a fixture state, not a leak. B owning versions
      // is normal; B owning *A's* versions is the defect.
      const data = await res.json();
      const groups = data.groups ?? [];
      for (const g of groups) {
        expect(g.profile_id, "B 读到了 A 的简历版本分组").not.toBe(pid);
      }
      const text = JSON.stringify(groups);
      expect(text, "响应里出现了 A 的 profile_id").not.toContain(pid);
    } else {
      expect([400, 403, 404]).toContain(res.status());
    }
    await ctx.dispose();
  });
});
