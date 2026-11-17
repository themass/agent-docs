import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

/**
 * Performance budget guards.
 *
 * These are source-level assertions, not Lighthouse runs: running Lighthouse in CI
 * needs a browser and minutes of wall clock, so the regression it protects against
 * would ship long before the check reported it. What can be checked instantly is the
 * *cause* that was measured and removed — and the cause is specific enough to pin.
 *
 * The measurement, for the record: `/guides/backend-engineer-resume` scored 72 with
 * 1,600ms total blocking time, and 99 with 20ms once `FeedbackLauncher` stopped
 * hydrating synchronously in the root layout. Nothing else moved. A future change that
 * imports it directly again would restore both the bundle and the blocking time, and
 * nothing in the type system would object.
 */

const ROOT = join(__dirname, "..");
const read = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("root layout payload", () => {
  test("the feedback launcher is deferred, never imported eagerly", () => {
    const layout = read("app/layout.tsx");
    // Direct import is what caused the regression; the deferred wrapper is the contract.
    expect(layout).not.toMatch(/from\s+["']@\/components\/feedback\/FeedbackLauncher["']/);
    expect(layout).toContain("DeferredFeedbackLauncher");
  });

  test("there is exactly one feedback launcher on the page", () => {
    const layout = read("app/layout.tsx");
    const mounts = layout.match(/<DeferredFeedbackLauncher\s*\/>/g) ?? [];
    expect(mounts).toHaveLength(1);
  });

  test("the deferred wrapper keeps a bounded fallback, not just requestIdleCallback", () => {
    const wrapper = read("components/feedback/DeferredFeedbackLauncher.tsx");
    // A browser that never goes idle must still get the button; "deferred" must not
    // silently become "absent" — that would fix the metric by removing the feature.
    expect(wrapper).toMatch(/requestIdleCallback/);
    expect(wrapper).toMatch(/setTimeout/);
    expect(wrapper).toMatch(/addEventListener\(["']load["']/);
  });

  test("the first template image is prioritized and the rest stay lazy", () => {
    const page = read("app/resume-template/page.tsx");
    // That image is the LCP element; measured LCP went 3.4s -> 3.0s with priority, and
    // the three images total 130KB, so leaving the others lazy keeps them off the
    // critical path rather than competing with it.
    expect(page).toMatch(/priority=\{index === 0\}/);
  });
});
