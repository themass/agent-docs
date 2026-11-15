import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * L. 性能门槛.
 *
 * These thresholds come from measured baselines (docs/operations/PERF-SUMMARY.md),
 * not from round numbers. Each one is set loose enough not to flake on a slow day
 * and tight enough to catch a regression of the kind that shipped: the call list
 * was 2.8s because 1.35MB of payload was fetched, and the metrics panel took 1.2s
 * for 21KB.
 *
 * They are ceilings, not targets. A number here going up is the signal.
 */

type Sample = { label: string; ms: number; kb: number };

async function timeRequest(
  page: Parameters<typeof login>[0],
  path: string,
  label: string,
): Promise<Sample> {
  const t0 = Date.now();
  const res = await page.request.get(new URL(path, page.url()).toString());
  const ms = Date.now() - t0;
  expect(res.status(), `${label} 返回 ${res.status()}`).toBe(200);
  const body = await res.text();
  return { label, ms, kb: Math.round(body.length / 102.4) / 10 };
}

test.describe("L. 性能门槛", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("L-05 管理后台调用列表 < 3s，且返回体不含 payload", async ({ page }) => {
    // Was 2818ms with 67.9KB before the payload columns were deferred, then 1784ms
    // after the count query was merged into the page query. 3s leaves room for a
    // slow link while still catching a return of either regression.
    const s = await timeRequest(page, "/api/v1/admin/llm/calls?limit=100", "llm/calls limit=100");
    expect(s.ms, `${s.label} 耗时 ${s.ms}ms（上限 3000）`).toBeLessThan(3000);
    // ~66KB for 100 rows of short columns is the *normal* size — the response model
    // never had the payload fields, so deferring them changed database time, not
    // wire size. If the payload columns ever reached the response it would be over a
    // megabyte, not a few KB more, so the ceiling is set to catch that, not to
    // measure the defer. K-14 asserts the fields are absent, which is the precise check.
    expect(s.kb, `${s.label} 返回 ${s.kb}KB，payload 列可能进了响应`).toBeLessThan(500);
  });

  test("L-02/L-05 监控面板接口 < 3s", async ({ page }) => {
    const s = await timeRequest(page, "/api/v1/admin/metrics", "admin/metrics");
    expect(s.ms, `${s.label} 耗时 ${s.ms}ms（上限 3000）`).toBeLessThan(3000);
  });

  test("L-02 主要页面首屏 < 8s", async ({ page }) => {
    const pages = ["/resume-agent", "/jobs", "/interviews", "/settings/account"];
    for (const path of pages) {
      const t0 = Date.now();
      await page.goto(path, { waitUntil: "domcontentloaded" });
      const ms = Date.now() - t0;
      // 8s is generous on purpose: this runs against a remote production site from
      // wherever CI sits. It catches "the page never loads", not micro-regressions.
      expect(ms, `${path} 首屏 ${ms}ms`).toBeLessThan(8000);
    }
  });

  test("L-06 连续三次列表请求不累积变慢", async ({ page }) => {
    // A leaking session or connection pool shows up as monotonic growth across
    // repeated identical requests, which a single-shot threshold cannot see.
    const times: number[] = [];
    for (let i = 0; i < 3; i++) {
      const s = await timeRequest(page, "/api/v1/admin/llm/calls?limit=50", `第 ${i + 1} 次`);
      times.push(s.ms);
    }
    const first = times[0];
    const last = times[times.length - 1];
    expect(last, `连续请求耗时 ${times.join(" / ")}ms，最后一次明显变慢`).toBeLessThan(first * 3 + 1000);
  });
});
