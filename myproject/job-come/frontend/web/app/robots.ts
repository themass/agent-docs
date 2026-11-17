import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/seo/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin/", "/api/", "/settings/", "/mock/", "/auth/", "/feedback/"],
      },
      // Explicit allow for the crawlers that feed AI answer engines (ChatGPT search,
      // Perplexity, Claude). The `*` rule above already permits them; naming them is how
      // intent is signalled and where we would narrow later. `public/llms.txt` is the
      // companion, and every serious competitor ships both.
      {
        userAgent: ["GPTBot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot"],
        allow: "/",
        disallow: ["/admin/", "/api/", "/settings/", "/mock/", "/auth/", "/feedback/"],
      },
      {
        userAgent: "Baiduspider",
        allow: "/",
        disallow: ["/admin/", "/api/", "/settings/", "/mock/", "/auth/", "/feedback/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
