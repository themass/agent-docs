// vitest runner (the repo's other tests are node:test .cjs files run separately;
// vitest only collects *.test.ts, so this file uses vitest's own API).
import { describe, expect, test } from "vitest";

import { ALL_GUIDES, GUIDES, guideBySlug, guideUrl } from "@/lib/seo/content";
import { PUBLIC_SITEMAP_PATHS } from "@/lib/seo/site";

/**
 * Guards on the content-cluster data, written against the two failure modes this site
 * has already lived through:
 *
 * 1. `/` silently vanishing from the sitemap while it was a redirect — a sitemap that
 *    omits the domain root quietly strands every inbound link for months.
 * 2. Pages that exist in data but not in the sitemap (or the reverse), which is how a
 *    sitemap starts lying and how crawlers stop trusting it.
 *
 * These are one-sided by construction if they only assert "the good thing is present";
 * the mutation checks at the bottom of this file deliberately break each invariant in a
 * copy of the data and re-run the same predicates, so a test that stopped being able to
 * fail would show up here rather than in production.
 */

function isKebabSlug(slug: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);
}

function validateGuides(guides: typeof GUIDES): string[] {
  const problems: string[] = [];
  const slugs = new Set<string>();
  for (const guide of guides) {
    if (!isKebabSlug(guide.slug)) problems.push(`${guide.slug}: slug not kebab-case`);
    if (slugs.has(guide.slug)) problems.push(`${guide.slug}: duplicate slug`);
    slugs.add(guide.slug);
    if (guide.title.length > 60) problems.push(`${guide.slug}: title too long for SERP`);
    if (guide.description.length > 160) problems.push(`${guide.slug}: description too long`);
    if (guide.sections.length < 3) problems.push(`${guide.slug}: thin page, <3 sections`);
    if (guide.faq.length < 2) problems.push(`${guide.slug}: <2 FAQ items for FAQPage markup`);
    for (const item of guide.faq) {
      if (item.q.length === 0 || item.a.length < 20) problems.push(`${guide.slug}: weak FAQ item`);
    }
    for (const related of guide.related ?? []) {
      if (!guides.some((g) => g.slug === related)) problems.push(`${guide.slug}: dangling related ${related}`);
    }
  }
  return problems;
}

test("every guide satisfies the publishing invariants", () => {
  expect(validateGuides(ALL_GUIDES)).toEqual([]);
});

test("guideBySlug and guideUrl agree with GUIDES", () => {
  expect(guideBySlug.size).toBe(ALL_GUIDES.length);
  for (const guide of ALL_GUIDES) {
    expect(guideBySlug.get(guide.slug)).toBe(guide);
    expect(guideUrl(guide.slug).startsWith("/guides/")).toBeTruthy();
  }
});

test("the sitemap covers the domain root and every published guide", () => {
  const paths = PUBLIC_SITEMAP_PATHS.map((entry) => entry.path);
  // The regression this pins: `/` was absent for as long as it was a redirect.
  expect(paths).toContain("/");
  expect(new Set(paths).size).toBe(paths.length);
  // Guide pages reach the sitemap through app/sitemap.ts importing GUIDES directly
  // (they are not in PUBLIC_SITEMAP_PATHS); what this list must stay free of is a
  // guide path hardcoded here that could drift from the data.
  for (const guide of ALL_GUIDES) {
    expect(paths).not.toContain(guideUrl(guide.slug));
  }
});

test("sitemap.ts emits exactly the product pages plus the guide cluster", async () => {
  const { default: sitemap } = await import("@/app/sitemap");
  const urls = sitemap().map((entry) => entry.url);
  expect(new Set(urls).size).toBe(urls.length);
  for (const guide of ALL_GUIDES) {
    expect(urls.some((u) => u.endsWith(guideUrl(guide.slug)))).toBeTruthy();
  }
  expect(urls.some((u) => u.endsWith("/guides"))).toBeTruthy();
  expect(urls.some((u) => /\/$/.test(u))).toBeTruthy();
});

/**
 * Mutation checks: the predicates above, run against deliberately broken data.
 * Each case must produce a problem string, or the guard has gone blind.
 */
test("guards still bite when the invariants are broken", () => {
  const base = structuredClone(GUIDES);
  const mutated = structuredClone(GUIDES);
  mutated[0].slug = "Bad_Slug";
  mutated[1].slug = mutated[0].slug;
  mutated[2].title = "x".repeat(80);
  mutated[3].description = "x".repeat(200);
  mutated[0].sections = mutated[0].sections.slice(0, 2);
  mutated[1].faq = [];
  mutated[2].related = ["nonexistent-guide"];
  const problems = validateGuides(mutated);
  expect(problems.some((p) => p.includes("not kebab-case"))).toBeTruthy();
  expect(problems.some((p) => p.includes("duplicate slug"))).toBeTruthy();
  expect(problems.some((p) => p.includes("title too long"))).toBeTruthy();
  expect(problems.some((p) => p.includes("description too long"))).toBeTruthy();
  expect(problems.some((p) => p.includes("thin page"))).toBeTruthy();
  expect(problems.some((p) => p.includes("<2 FAQ"))).toBeTruthy();
  expect(problems.some((p) => p.includes("dangling related"))).toBeTruthy();
  // Sanity that the fixture itself was sound before mutation.
  expect(validateGuides(base)).toEqual([]);
});
