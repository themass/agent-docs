import type { MetadataRoute } from "next";

import { ALL_GUIDES, guideUrl } from "@/lib/seo/content";
import { PUBLIC_SITEMAP_PATHS, SITE_URL } from "@/lib/seo/site";

/**
 * Product routes come from `PUBLIC_SITEMAP_PATHS`; guides come from the same data the
 * pages render from, so a page cannot exist without being listed (and cannot be listed
 * without existing) — the mismatch is how a sitemap starts lying.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const entries: MetadataRoute.Sitemap = PUBLIC_SITEMAP_PATHS.map((entry) => ({
    url: `${SITE_URL}${entry.path}`,
    lastModified,
    changeFrequency: entry.changeFrequency,
    priority: entry.priority,
  }));
  // The index page outranks its own articles (it is the cluster hub), and articles sit
  // below the product pages because a guide converts less directly — its job is the
  // visitor who has not decided on a tool yet.
  entries.push({
    url: `${SITE_URL}/guides`,
    lastModified,
    changeFrequency: "monthly",
    priority: 0.8,
  });
  for (const guide of ALL_GUIDES) {
    entries.push({
      url: `${SITE_URL}${guideUrl(guide.slug)}`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.7,
    });
  }
  return entries;
}
